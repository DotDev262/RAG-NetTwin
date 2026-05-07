import math
import pandas as pd
from typing import List, Dict

try:
    from scipy.stats import norm

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class StatsReporter:
    """
    Computes and generates summary tables for evaluation results.
    """

    def compute_wilson_ci(
        self, count: int, total: int, confidence: float = 0.95
    ) -> str:
        if total == 0:
            return "N/A"
        z = 1.96  # 95% confidence
        p = count / total
        denominator = 1 + z**2 / total
        centre_prob = p + z**2 / (2 * total)
        std_dev = math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total)
        upper = (centre_prob + z * std_dev) / denominator
        return f"{p*100:.1f}% (±{(upper-p)*100:.1f}%)"

    def compute_p_value(self, count1: int, n1: int, count2: int, n2: int) -> str:
        if not SCIPY_AVAILABLE or n1 == 0 or n2 == 0:
            return "N/A"

        p1 = count1 / n1
        p2 = count2 / n2
        p_combined = (count1 + count2) / (n1 + n2)
        if p_combined == 0 or p_combined == 1:
            return "1.0000"

        z = (p1 - p2) / math.sqrt(p_combined * (1 - p_combined) * (1 / n1 + 1 / n2))
        p_val = 2 * (1 - norm.cdf(abs(z)))
        return f"{p_val:.4f}"

    def generate_summary_table(
        self, results: List[Dict], retrieval_mode: str = "tiered"
    ):
        summary = []
        mode_counts = {}
        for mode in ["vanilla", "rag_nettwin"]:
            mode_data = []
            for r in results:
                if mode in r and isinstance(r[mode], dict):
                    mode_data.append(r[mode])

            if not mode_data:
                continue

            n = len(mode_data)
            strict_pass_count = 0
            gap_count = 0
            fail_count = 0

            for d in mode_data:
                status = d.get("status")
                if not status and "validation" in d:
                    status = d["validation"].get("status")

                if status in ["PASS", "WARNING"]:
                    strict_pass_count += 1
                elif status == "REJECT_FOR_MANUAL_REVIEW":
                    gap_count += 1
                elif status == "FAIL":
                    fail_count += 1

            cfr_success = sum(1 for d in mode_data if not d.get("cfr_failure", False))
            functional_pass = sum(
                1 for d in mode_data if d.get("functional_status") == "PASS"
            )

            # GNS3 Metrics (Recommendation CAR & ISR)
            gns3_data = [
                d for d in mode_data if d.get("functional_status") != "SKIPPED"
            ]
            car_sum = sum(d.get("car", 0.0) for d in gns3_data)
            avg_car = (car_sum / len(gns3_data)) if gns3_data else 0.0

            # Interoperability Success Rate (ISR)
            multi_vendor_data = [d for d in gns3_data if d.get("is_multi_vendor")]
            isr_pass = sum(
                1 for d in multi_vendor_data if d.get("functional_status") == "PASS"
            )
            isr_rate = (isr_pass / len(multi_vendor_data)) if multi_vendor_data else 0.0

            if mode == "vanilla":
                hal_count = sum(
                    1
                    for d in mode_data
                    if d.get("hallucination", {}).get("is_hallucinated")
                )
            else:
                hal_count = sum(
                    1
                    for d in mode_data
                    if any(
                        h.get("is_hallucinated") for h in d.get("hallucinations", [])
                    )
                )

            mode_counts[mode] = {"strict_pass": strict_pass_count, "n": n}
            display_mode = mode if mode == "vanilla" else f"RAG ({retrieval_mode})"

            summary.append(
                {
                    "Mode": display_mode,
                    "N": n,
                    "Strict SV": self.compute_wilson_ci(strict_pass_count, n),
                    "PEA (CFR)": self.compute_wilson_ci(cfr_success, n),
                    "GNS3 CAR": f"{avg_car*100:.1f}%",
                    "GNS3 ISR": f"{isr_rate*100:.1f}%" if multi_vendor_data else "N/A",
                    "Functional": self.compute_wilson_ci(functional_pass, n),
                    "Hallucination": f"{(hal_count / n) * 100:.1f}%",
                }
            )

        print("\n" + "=" * 100)
        print(f"{'PHASE 1 RESEARCH EVALUATION SUMMARY':^100}")
        print("=" * 100)
        df = pd.DataFrame(summary)
        print(df.to_string(index=False))
        print("-" * 100)
        if "vanilla" in mode_counts and "rag_nettwin" in mode_counts:
            p_val = self.compute_p_value(
                mode_counts["rag_nettwin"]["strict_pass"],
                mode_counts["rag_nettwin"]["n"],
                mode_counts["vanilla"]["strict_pass"],
                mode_counts["vanilla"]["n"],
            )
            print(f"Strict Syntactic Validity Improvement (p-value): {p_val}")
        print("=" * 100)
        print(
            "Note: Strict SV: Batfish Verified (PASS/WARNING). Gap Rate: Tool limitations (REJECT)."
        )
        print(
            "PEA (Parameter Extraction Accuracy): config alignment with intent (CFR)."
        )
        print("=" * 100 + "\n")
