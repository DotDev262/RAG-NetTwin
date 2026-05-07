from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.schemas.intent import StructuredIntent


class NetworkValidator(ABC):
    """Abstract Base Class for all network configuration validators."""

    def __init__(self, tier: int):
        self.tier = tier

    @abstractmethod
    def validate(
        self, configs: Dict[str, str], intent: Optional[StructuredIntent] = None
    ) -> Dict[str, Any]:
        """
        Validate the generated configurations against the user's intent.

        Args:
            configs: Dictionary mapping device names to CLI configurations.
            intent: The StructuredIntent object representing the user's request.

        Returns:
            A dictionary containing the validation results (status, message, etc.).
        """
        pass

    def get_tier_info(self) -> Dict[str, Any]:
        """Returns metadata about the validation tier."""
        return {"tier": self.tier, "type": self.__class__.__name__}
