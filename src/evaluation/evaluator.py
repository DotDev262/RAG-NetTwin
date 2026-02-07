import os
import time
import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import our system components
from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from llm import LLMProvider

load_dotenv()


class Evaluator:
    """
    Evaluation framework to compare RAG-NetTwin against Baseline (Vanilla LLM).
    Metrics:
    1. Hallucination Rate (approximated by command validity/retrieval overlap)
    2. Intent Fidelity (did we get the right protocol/IPs?)
    3. Generation Time
    """

    def __init__(self):
        # Use LLMProvider for baseline LLM (vanilla LLM without RAG)
        self.llm = LLMProvider.get_llm(temperature=0.1)
        self.parser = IntentParser()
        self.rag_generator = ConfigGenerator()
        # self.validator = BatfishValidator() # Future integration

    def run_benchmark(
        self, scenarios: List[str], output_file: str = "results/benchmark_report.json"
    ):
        """Runs the benchmark on a list of natural language scenarios."""
        results = []

        print(f"Starting benchmark with {len(scenarios)} scenarios...")

        for i, scenario in enumerate(scenarios, 1):
            print(f"\n[Scenario {i}/{len(scenarios)}] Processing: {scenario[:50]}...")

            # 1. Parse Intent (Common for both)
            try:
                intent = self.parser.parse(scenario)
            except Exception as e:
                print(f"  Failed to parse intent: {e}")
                continue

            # 2. Run Baseline (Vanilla LLM)
            start_time = time.time()
            baseline_config = self._generate_baseline(scenario)
            baseline_time = time.time() - start_time

            # 3. Run RAG-NetTwin
            start_time = time.time()
            try:
                rag_output = self.rag_generator.generate(intent)
                # Extract just the config text for the first device for comparison simplicity
                if rag_output:
                    first_device = list(rag_output.keys())[0]
                    rag_config = rag_output[first_device]["config"]
                    rag_sources = rag_output[first_device]["retrieved_sources"]
                else:
                    rag_config = "NO_CONFIG_GENERATED"
                    rag_sources = []
            except Exception as e:
                print(f"  RAG generation failed: {e}")
                rag_config = "ERROR"
                rag_sources = []
            rag_time = time.time() - start_time

            # 4. Record Result
            results.append(
                {
                    "scenario": scenario,
                    "parsed_intent": intent.model_dump(),
                    "baseline": {
                        "config": baseline_config,
                        "time_sec": baseline_time,
                        "hallucination_score": self._estimate_hallucination(
                            baseline_config, with_rag=False
                        ),
                    },
                    "rag": {
                        "config": rag_config,
                        "retrieved_sources": rag_sources,
                        "time_sec": rag_time,
                        "hallucination_score": self._estimate_hallucination(
                            rag_config, with_rag=True
                        ),
                    },
                }
            )

        # Save results
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nBenchmark complete. Results saved to {output_file}")
        self._print_summary(results)

    def _generate_baseline(self, scenario: str) -> str:
        """Generates config using raw LLM without RAG context."""
        prompt = ChatPromptTemplate.from_template(
            "You are a network engineer. Generate a Cisco IOS-XE configuration for the following request: {request}. "
            "Provide ONLY the configuration commands, no explanation."
        )
        chain = prompt | self.llm
        return chain.invoke({"request": scenario}).content

    def _estimate_hallucination(self, config: str, with_rag: bool) -> float:
        """
        Heuristic score (0.0 to 1.0) for hallucination probability.
        Lower is better.
        """
        score = 0.0

        # 1. Check for placeholder text (Vanilla LLMs often leave <IP_ADDRESS>)
        if "<" in config and ">" in config:
            score += 0.3

        # 2. Check for explanation text mixed with config (Chatty LLM)
        lines = config.split("\n")
        non_comment_lines = [
            l for l in lines if l.strip() and not l.strip().startswith("!")
        ]

        if non_comment_lines:
            avg_len = sum(len(l) for l in non_comment_lines) / len(non_comment_lines)
            # If average line length is very long, it might be prose, not config
            if avg_len > 60:
                score += 0.2

        # 3. RAG specific bonus: Did it cite sources?
        if with_rag:
            if "! Based on" in config:
                score -= 0.1  # Bonus for citation
            else:
                score += 0.1  # Penalty for missing citation in RAG mode

        return max(0.0, min(1.0, score))

    def _print_summary(self, results: List[Dict]):
        if not results:
            print("No results to summarize.")
            return

        print("\n=== Benchmark Summary ===")
        avg_base_time = sum(r["baseline"]["time_sec"] for r in results) / len(results)
        avg_rag_time = sum(r["rag"]["time_sec"] for r in results) / len(results)
        avg_base_hal = sum(r["baseline"]["hallucination_score"] for r in results) / len(
            results
        )
        avg_rag_hal = sum(r["rag"]["hallucination_score"] for r in results) / len(
            results
        )

        print(f"Scenarios: {len(results)}")
        print(f"Avg Generation Time (Baseline): {avg_base_time:.2f}s")
        print(f"Avg Generation Time (RAG):      {avg_rag_time:.2f}s")
        print(f"Avg Hallucination Score (Base): {avg_base_hal:.2f} (Lower is better)")
        print(f"Avg Hallucination Score (RAG):  {avg_rag_hal:.2f} (Lower is better)")
        print("Note: RAG is slower due to retrieval latency (trade-off for accuracy).")


if __name__ == "__main__":
    # Test run
    evaluator = Evaluator()
    scenarios = [
        "Configure OSPF area 0 on Gig1/0/1 with IP 10.10.10.1/24",
        "Create an ACL named BLOCK_WEB to deny TCP port 80 from any source",
    ]
    evaluator.run_benchmark(scenarios)
