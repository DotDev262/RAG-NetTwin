from typing import Dict, Any, Optional, cast
from langchain_core.prompts import ChatPromptTemplate
from src.llm import LLMProvider
import json
from src.utils import setup_logger

logger = setup_logger("BlastRadiusAnalyzer")


class BlastRadiusAnalyzer:
    """
    Analyzes the 'Blast Radius' of a network change by comparing pre/post states (Recommendation 3).
    """

    def __init__(self, model_name: Optional[str] = None):
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.0)

    def analyze(
        self, intent_text: str, pre_state: Dict[str, Any], post_state: Dict[str, Any]
    ) -> str:
        """
        Uses an LLM to diff the network states and summarize the impact.
        """
        logger.info("Analyzing Blast Radius...")

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a Senior Network Reliability Engineer. Your task is to analyze 'Pre' and 'Post' "
                    "network snapshots to determine the impact (Blast Radius) of a change.\n\n"
                    "RULES:\n"
                    "1. Identify specifically what changed (Intended Changes).\n"
                    "2. Identify any unintended collateral damage (e.g., lost routes, down interfaces).\n"
                    "3. Provide a concise, professional summary for a Change Management report.",
                ),
                (
                    "human",
                    "### ORIGINAL INTENT ###\n{intent}\n\n"
                    "### PRE-CHANGE SNAPSHOT ###\n{pre}\n\n"
                    "### POST-CHANGE SNAPSHOT ###\n{post}\n\n"
                    "### ANALYSIS ###\n"
                    "Please provide your Blast Radius analysis in Markdown format.",
                ),
            ]
        )

        try:
            chain = prompt | self.llm
            response = chain.invoke(
                {
                    "intent": intent_text,
                    "pre": json.dumps(pre_state, indent=2),
                    "post": json.dumps(post_state, indent=2),
                }
            )
            return cast(str, response.content)
        except Exception as e:
            logger.error(f"Blast Radius analysis failed: {e}")
            return f"Analysis Error: {str(e)}"
