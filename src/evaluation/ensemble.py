from typing import List, Dict, Any, Optional, cast
from pydantic import BaseModel
from src.llm import LLMProvider
from src.rag.config_generator import ConfigGenerator
from src.schemas.intent import StructuredIntent
from src.utils import setup_logger

logger = setup_logger("EnsembleEngine")


class EnsembleResult(BaseModel):
    winner_config: str
    rationale: str
    consistency_score: float


class EnsembleJudgeResponse(BaseModel):
    winner_index: int
    rationale: str
    consistency_score: float


class EnsembleEngine:
    """
    Ensemble engine for multi-model voting.
    Generates configs using multiple models and uses a judge to select the best.
    """

    def __init__(self, models: Optional[List[str]] = None):
        self.models = models or ["openai/gpt-oss-120b", "gemini-1.5-flash"]
        self.judge = LLMProvider.get_llm(model="openai/gpt-oss-120b", temperature=0)

    def generate_and_vote(
        self, intent: StructuredIntent, context_map: Dict[str, Any]
    ) -> Dict[str, EnsembleResult]:
        """
        1. Generate candidates from multiple models.
        2. Use a judge to compare and vote.
        """
        results: Dict[str, EnsembleResult] = {}

        # This is a simplified version. In real research, we'd run full RAG for each model.
        # Here we assume we already have candidates or we generate them.

        for device in intent.devices:
            candidates: List[Dict[str, Any]] = []
            device_name = device.name or "Unknown-Device"
            for model in self.models:
                generator = ConfigGenerator(model_name=model)
                # Hacky: we only want one device's config here
                # In real research, we'd refactor ConfigGenerator to support single-device generation
                out = generator.generate(intent)
                if device_name in out:
                    candidates.append(
                        {"model": model, "config": out[device_name]["config"]}
                    )

            # Vote
            if candidates:
                winner = self._vote(device_name, candidates, intent.original_text or "")
                results[device_name] = winner

        return results

    def _vote(
        self, device_name: str, candidates: List[Dict[str, Any]], intent_text: str
    ) -> EnsembleResult:
        prompt = f"""You are a Senior Network Architect. Compare the following CLI configuration candidates for {device_name}.
Intent: {intent_text}

Candidates:
"""
        for i, c in enumerate(candidates):
            prompt += (
                f"\n--- Candidate {i + 1} (Model: {c['model']}) ---\n{c['config']}\n"
            )

        prompt += """
Select the most accurate and syntactically correct configuration. 
Provide your response as a JSON object with winner_index, rationale, and consistency_score.
"""
        try:
            # Use structured output for the judge
            structured_judge = LLMProvider.get_structured_llm(
                schema=EnsembleJudgeResponse,
                model="openai/gpt-oss-120b",
                temperature=0,
            )
            response = cast(EnsembleJudgeResponse, structured_judge.invoke(prompt))

            # Map back to EnsembleResult
            # Subtract 1 because winner_index is 1-based in the prompt instructions
            winner_idx = response.winner_index - 1
            if 0 <= winner_idx < len(candidates):
                winner_config = candidates[winner_idx]["config"]
            else:
                logger.warning(
                    f"Judge returned invalid winner_index {response.winner_index}, falling back to candidate 0"
                )
                winner_config = candidates[0]["config"]

            logger.info(f"Ensemble vote completed for {device_name}")
            return EnsembleResult(
                winner_config=winner_config,
                rationale=response.rationale,
                consistency_score=response.consistency_score,
            )
        except Exception as e:
            logger.error(f"Ensemble vote failed for {device_name}: {e}")
            # Robust fallback to first candidate
            return EnsembleResult(
                winner_config=candidates[0]["config"],
                rationale=f"Fallback due to judge error: {e}",
                consistency_score=0.5,
            )
