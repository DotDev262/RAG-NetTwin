from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from src.llm import LLMProvider
from src.utils import with_retry


class QueryExpander:
    """
    Expands a single user intent into multiple semantic search queries
    to improve retrieval recall.
    """

    def __init__(self, model_name: Optional[str] = None):
        # Use a fast model for query expansion
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.2)
        self.output_parser = CommaSeparatedListOutputParser()

    @with_retry(max_retries=3)
    def expand(self, query: str) -> List[str]:
        """
        Generates 3 variations of the input query.
        """
        prompt = ChatPromptTemplate.from_template(
            "You are a network engineering search assistant. "
            "Given the following network intent, generate 3 short, distinct search queries "
            "that would help find relevant technical documentation for CLI commands. "
            "Output ONLY the queries separated by commas.\n\n"
            "Intent: {query}\n"
            "Queries:"
        )

        chain = prompt | self.llm | self.output_parser
        try:
            expanded = chain.invoke({"query": query})
            # Clean up and ensure we include the original query
            results = [query]
            for q in expanded:
                q_clean = q.strip()
                if q_clean and q_clean not in results:
                    results.append(q_clean)
            return results[:4]  # Original + 3 expansions
        except Exception:
            return [query]
