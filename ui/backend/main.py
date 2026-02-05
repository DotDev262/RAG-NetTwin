from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parser.intent_parser import IntentParser, StructuredIntent
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator

app = FastAPI(title="RAG-NetTwin API", description="Backend for Hallucination-Mitigated IBN")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize modules
try:
    parser = IntentParser()
    generator = ConfigGenerator()
    validator = BatfishValidator()
except Exception as e:
    print(f"Warning during initialization: {e}")
    # We allow app to start even if keys are missing so user can see error in API

class IntentRequest(BaseModel):
    text: str

class ValidationRequest(BaseModel):
    configs: Dict[str, str]

@app.get("/")
async def root():
    return {"message": "Welcome to RAG-NetTwin API", "status": "online"}

@app.post("/parse")
async def parse_intent(request: IntentRequest):
    try:
        return parser.parse(request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate")
async def generate_config(intent: StructuredIntent):
    try:
        return generator.generate(intent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate")
async def validate_config(request: ValidationRequest):
    try:
        return validator.validate(request.configs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process")
async def end_to_end_process(request: IntentRequest):
    """Full pipeline: Parse -> Generate -> Validate"""
    try:
        # 1. Parse
        intent = parser.parse(request.text)
        
        # 2. Generate
        configs_output = generator.generate(intent)
        
        # 3. Validate
        # Extract just the config strings for the validator
        config_map = {name: data['config'] for name, data in configs_output.items()}
        validation_report = validator.validate(config_map)
        
        return {
            "intent": intent,
            "generated_configs": configs_output,
            "validation": validation_report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
