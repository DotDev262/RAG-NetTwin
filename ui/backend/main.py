from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parser.intent_parser import IntentParser, StructuredIntent
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from validation.containerlab_validator import ContainerlabValidator

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
    validator_t1 = BatfishValidator()
    validator_t2 = ContainerlabValidator()
except Exception as e:
    print(f"Warning during initialization: {e}")

class IntentRequest(BaseModel):
    text: str = Field(..., max_length=500, description="The network intent in natural language")

    @validator('text')
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Intent cannot be empty")
        
        # Basic prompt injection guardrails
        forbidden_phrases = [
            "ignore previous instructions", 
            "system prompt", 
            "you are a hacked",
            "delete all files"
        ]
        
        lower_v = v.lower()
        for phrase in forbidden_phrases:
            if phrase in lower_v:
                raise ValueError(f"Security blocked: Potentially unsafe content detected.")
                
        return v

@app.post("/process")
async def end_to_end_process(request: IntentRequest):
    """Full pipeline: Parse -> Generate -> Validate (Tier 1 & 2)"""
    try:
        # 1. Parse
        intent = parser.parse(request.text)
        
        # 2. Generate
        configs_output = generator.generate(intent)
        
        # 3. Validate
        config_map = {name: data['config'] for name, data in configs_output.items()}
        
        # Tier 1: Batfish
        report_t1 = validator_t1.validate(config_map)
        
        # Tier 2: Containerlab
        report_t2 = validator_t2.validate(config_map, intent)
        
        return {
            "intent": intent,
            "generated_configs": configs_output,
            "validation": {
                "tier1": report_t1,
                "tier2": report_t2
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
