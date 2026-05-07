from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any
import uuid
import time

# Add src to path

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from validation.containerlab_validator import ContainerlabValidator
from src.utils import setup_logger

logger = setup_logger("Backend")
app = FastAPI(
    title="RAG-NetTwin API", description="Backend for Hallucination-Mitigated IBN"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for job results (for research purposes, replace with DB for production)
jobs: Dict[str, Dict[str, Any]] = {}

# Initialize modules
try:
    parser = IntentParser()
    generator = ConfigGenerator()
    validator_t1 = BatfishValidator()
    validator_t2 = ContainerlabValidator()
except Exception as e:
    logger.error(f"Initialization failed: {e}")


class IntentRequest(BaseModel):
    text: str = Field(
        ..., max_length=500, description="The network intent in natural language"
    )

    @field_validator("text")
    @classmethod
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Intent cannot be empty")

        # Basic prompt injection guardrails
        forbidden_phrases = [
            "ignore previous instructions",
            "system prompt",
            "delete all files",
        ]
        lower_v = v.lower()
        if any(p in lower_v for p in forbidden_phrases):
            raise ValueError("Security blocked: Potentially unsafe content detected.")
        return v


async def run_pipeline(job_id: str, intent_text: str):
    """Asynchronous background task for the full pipeline with self-correction."""
    try:
        jobs[job_id]["status"] = "parsing"
        intent = parser.parse(intent_text)
        jobs[job_id]["intent"] = intent.model_dump()

        jobs[job_id]["status"] = "generating"
        configs_output = generator.generate(intent)

        # --- REFLECTION LOOP (Self-Correction) ---
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            jobs[job_id]["status"] = f"validating_t1_attempt_{attempt + 1}"
            config_map = {name: data["config"] for name, data in configs_output.items()}
            report_t1 = validator_t1.validate(config_map, intent)
            jobs[job_id]["validation_t1"] = report_t1

            if report_t1["status"] in ["PASS", "WARNING"]:
                logger.info(f"Job {job_id} passed validation on attempt {attempt + 1}")
                break

            if attempt < MAX_RETRIES - 1:
                logger.info(
                    f"Job {job_id} failed validation. Attempting self-correction {attempt + 1}/{MAX_RETRIES}"
                )
                jobs[job_id]["status"] = f"correcting_attempt_{attempt + 1}"

                refined_configs = {}
                for dev_name, config_data in configs_output.items():
                    # Identify errors for this device from Batfish issues
                    # Batfish issues now include the filename (sanitized name + .cfg)
                    safe_name = dev_name.replace("/", "_").replace("\\", "_")
                    dev_errors = [
                        i["details"]
                        for i in report_t1.get("issues", [])
                        if safe_name in i.get("details", "")
                    ]

                    if dev_errors:
                        # Find vendor
                        vendor = "cisco"
                        os_version = "17.6"
                        for d in intent.devices:
                            if d.name == dev_name:
                                vendor = d.vendor or "cisco"
                                os_version = d.os_version or "17.6"
                                break

                        refined_config = generator.refine(
                            dev_name,
                            config_data["config"],
                            "\n".join(dev_errors[:3]),
                            vendor,
                            os_version,
                        )
                        refined_configs[dev_name] = {
                            **config_data,
                            "config": refined_config,
                        }
                    else:
                        refined_configs[dev_name] = config_data

                configs_output = refined_configs
        # ----------------------------------------

        jobs[job_id]["generated_configs"] = configs_output

        # Only run T2 if T1 passes or with warning (to save resources)
        if jobs[job_id]["validation_t1"]["status"] in ["PASS", "WARNING"]:
            jobs[job_id]["status"] = "validating_t2"
            config_map = {name: data["config"] for name, data in configs_output.items()}
            report_t2 = validator_t2.validate(config_map, intent)
            jobs[job_id]["validation_t2"] = report_t2
        else:
            jobs[job_id]["validation_t2"] = {
                "status": "SKIPPED",
                "reason": "Tier 1 failed after retries",
            }

        jobs[job_id]["status"] = "completed"
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


@app.post("/process")
async def start_process(request: IntentRequest, background_tasks: BackgroundTasks):
    """Starts the full pipeline as a background task."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "created_at": time.time(),
        "intent_text": request.text,
    }
    background_tasks.add_task(run_pipeline, job_id, request.text)
    return {"job_id": job_id, "status": "queued"}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Retrieves the status and results of a background job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
