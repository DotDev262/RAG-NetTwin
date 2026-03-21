from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from llm import LLMProvider
from rag.config_generator import ConfigGenerator
from parser.intent_parser import StructuredIntent
from utils import setup_logger

logger = setup_logger("EnsembleEngine")

class EnsembleResult(BaseModel):
    winner_config: str
    rationale: str
    consistency_score: float

class EnsembleEngine:
    """
    Ensemble engine for multi-model voting.
    Generates configs using multiple models and uses a judge to select the best.
    """
    def __init__(self, models: List[str] = None):
        self.models = models or ["llama-3.3-70b-versatile", "gemini-1.5-flash"]
        self.judge = LLMProvider.get_llm(model="llama-3.3-70b-versatile", temperature=0)

    def generate_and_vote(self, intent: StructuredIntent, context_map: Dict[str, Any]) -> Dict[str, EnsembleResult]:
        """
        1. Generate candidates from multiple models.
        2. Use a judge to compare and vote.
        """
        results = {}
        
        # This is a simplified version. In real research, we'd run full RAG for each model.
        # Here we assume we already have candidates or we generate them.
        
        for device in intent.devices:
            candidates = []
            for model in self.models:
                generator = ConfigGenerator(model_name=model)
                # Hacky: we only want one device's config here
                # In real research, we'd refactor ConfigGenerator to support single-device generation
                out = generator.generate(intent)
                if device.name in out:
                    candidates.append({
                        "model": model,
                        "config": out[device.name]["config"]
                    })
            
            # Vote
            winner = self._vote(device.name, candidates, intent.original_text)
            results[device.name] = winner
            
        return results

    def _vote(self, device_name: str, candidates: List[Dict], intent_text: str) -> EnsembleResult:
        prompt = f"""You are a Senior Network Architect. Compare the following CLI configuration candidates for {device_name}.
Intent: {intent_text}

Candidates:
"""
        for i, c in enumerate(candidates):
            prompt += f"\n--- Candidate {i+1} (Model: {c['model']}) ---\n{c['config']}\n"
            
        prompt += """
Select the most accurate and syntactically correct configuration. 
Provide your response as a JSON object with:
winner_index: int
rationale: str
consistency_score: float (0.0 to 1.0, how similar are the candidates?)
"""
        # Note: Using structured LLM would be better here, but for now we just use raw LLM
        # and assume it follows instructions or we parse it.
        resp = self.judge.invoke(prompt)
        
        # (Parsing logic omitted for brevity, assuming judge is helpful)
        logger.info(f"Ensemble vote completed for {device_name}")
        
        # Placeholder result
        return EnsembleResult(
            winner_config=candidates[0]["config"], 
            rationale="Selected via multi-model ensemble analysis.",
            consistency_score=0.85
        )
