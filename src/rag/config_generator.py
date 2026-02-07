import os
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
import json

from rag.vector_store import VectorStore
from parser.intent_parser import StructuredIntent
from config import settings
from llm import LLMProvider


class ConfigGenerator:
    """Generates network configurations using RAG and LLM."""

    def __init__(self, model_name: str = None):
        # Use LLMProvider to get the appropriate LLM instance
        self.llm = LLMProvider.get_llm(
            model=model_name, temperature=settings.temperature
        )
        self.vector_store = VectorStore()

    def generate(self, structured_intent: StructuredIntent) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device in the intent.
        Returns a dictionary mapping device name to generated config.
        """
        configs = {}

        for device in structured_intent.devices:
            # Normalize OS version for retrieval
            search_version = device.os_version
            if device.os_type == "ios-xe" and "17.6" in search_version:
                search_version = "ios-xe-17.6"
            elif device.vendor == "cisco" and (
                "15." in search_version or "ios-15" in search_version.lower()
            ):
                search_version = "ios-15.6"
            elif device.os_type == "junos" and "21.4" in search_version:
                search_version = "junos-21.4"

            # 1. Retrieve relevant context
            query = (
                f"{structured_intent.protocol} {structured_intent.action} "
                + " ".join(structured_intent.parameters.keys())
            )

            # Try with OS version filter first
            context_results = self.vector_store.retrieve(
                query=query,
                os_version=search_version,
                n_results=15,
            )

            # If no results with OS filter, try without
            if not context_results:
                print(
                    f"      ⚠️  No results with OS filter '{search_version}', trying without filter..."
                )
                context_results = self.vector_store.retrieve(
                    query=query,
                    n_results=15,
                )

            # If still no results, try a broader query
            if not context_results:
                print(f"      ⚠️  Trying broader query...")
                broad_query = f"{structured_intent.protocol} configuration"
                context_results = self.vector_store.retrieve(
                    query=broad_query,
                    n_results=15,
                )

            context_text = self._format_context(context_results)

            # 2. Build prompt
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", self._get_system_prompt()),
                    (
                        "human",
                        "Intent: {intent}\n\nRetrieved Vendor Documentation:\n{context}\n\nGenerate the configuration for device {device_name} ({vendor} {os_type} {os_version}).",
                    ),
                ]
            )

            # 3. Generate
            chain = prompt | self.llm
            response = chain.invoke(
                {
                    "intent": structured_intent.model_dump_json(indent=2),
                    "context": context_text,
                    "device_name": device.name,
                    "vendor": device.vendor,
                    "os_type": device.os_type,
                    "os_version": device.os_version,
                }
            )

            configs[device.name] = {
                "config": response.content,
                "retrieved_sources": [r["id"] for r in context_results],
            }

        return configs

    def _format_context(self, results: List[Dict]) -> str:
        formatted = ""
        for i, res in enumerate(results, 1):
            formatted += f"Reference [{res['id']}]:\n{res['text']}\n{'-' * 40}\n"
        return formatted

    def _get_system_prompt(self) -> str:
        return """You are a highly precise Network Configuration Generator. 
Your task is to generate CLI commands based ONLY on the provided Intent and the Retrieved Vendor Documentation.

CRITICAL RULES:
1. Provide ONLY the configuration commands. MINIMAL explanation.
2. Use ONLY the syntax found in the retrieved documentation.
3. If the documentation does not contain the necessary commands, state "INSUFFICIENT_CONTEXT".
4. DO NOT hallucinate commands or parameters.
5. For every significant command block, add a comment citing the Reference ID, e.g., ! Based on [chunk_000123]
6. Target the specific OS version mentioned in the intent.
7. Output format should be pure CLI, ready to be pasted into a terminal.
"""


if __name__ == "__main__":
    # Test generation (requires API key and vector store population)
    from parser.intent_parser import DeviceIntent, StructuredIntent

    test_intent = StructuredIntent(
        protocol="OSPF",
        action="create",
        devices=[
            DeviceIntent(
                name="Router-1",
                vendor="cisco",
                os_type="ios-xe",
                os_version="ios-xe-17.6",
            )
        ],
        parameters={
            "process_id": "1",
            "area": "0",
            "interface": "Gig0/1",
            "ip": "192.168.1.1/24",
        },
        requirements=["enable_ospf", "set_area"],
    )

    try:
        generator = ConfigGenerator()
        result = generator.generate(test_intent)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
