from pydantic import BaseModel
from typing import Dict


class TokenUsage(BaseModel):
    """
    Pydantic model for tracking token usage.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_est: float = 0.0


class TokenCounter:
    """
    Tracks token usage across the research lifecycle.
    """

    def __init__(self) -> None:
        self.session_usage: Dict[str, TokenUsage] = {}

    def add_usage(
        self, call_id: str, prompt: int, completion: int, model: str = "llama3"
    ) -> None:
        usage = TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
        rates = {"llama3": 0.05, "gemini": 0.10}
        rate = rates.get(model.lower(), 0.05)
        usage.cost_est = (usage.total_tokens / 1_000_000) * rate
        self.session_usage[call_id] = usage

    def get_total_usage(self) -> TokenUsage:
        total = TokenUsage()
        for u in self.session_usage.values():
            total.prompt_tokens += u.prompt_tokens
            total.completion_tokens += u.completion_tokens
            total.total_tokens += u.total_tokens
            total.cost_est += u.cost_est
        return total
