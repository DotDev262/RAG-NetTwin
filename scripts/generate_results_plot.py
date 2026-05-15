import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import json
import os
import matplotlib.pyplot as plt  # type: ignore
import pandas as pd
import seaborn as sns  # type: ignore

# Set professional style
sns.set_theme(style="whitegrid")
plt.rcParams.update({"font.size": 10, "font.family": "sans-serif"})


def load_data(filepath="results/paper_evaluation_latest.json"):
    if not os.path.exists(filepath):
        print(
            f"Error: {filepath} not found. Please run 'uv run python run_paper_eval.py' first."
        )
        return None

    with open(filepath, "r") as f:
        return json.load(f)


def generate_performance_plot(data):
    results = data.get("results", [])
    if not results:
        print("No results found in data.")
        return

    # Aggregate metrics
    summary = []
    for mode in ["vanilla", "rag_nettwin"]:
        mode_data = [
            r[mode] for r in results if mode in r and r[mode].get("status") != "ERROR"
        ]
        if not mode_data:
            continue

        # Syntactic Validity
        pass_count = 0
        for d in mode_data:
            status = d.get("status") or d.get("validation", {}).get("status")
            if status in ["PASS", "WARNING"]:
                pass_count += 1

        # Hallucination Rate (Inverse for plot)
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
                if any(h.get("is_hallucinated") for h in d.get("hallucinations", []))
            )

        # CFR Faithfulness
        cfr_count = sum(1 for d in mode_data if d.get("cfr_failure", False))

        summary.append(
            {
                "Mode": "Vanilla LLM" if mode == "vanilla" else "RAG-NetTwin",
                "Syntactic Validity": (pass_count / len(mode_data)) * 100,
                "Hallucination-Free": ((len(mode_data) - hal_count) / len(mode_data))
                * 100,
                "CFR Faithfulness": ((len(mode_data) - cfr_count) / len(mode_data))
                * 100,
            }
        )

    df = pd.DataFrame(summary).melt(
        id_vars="Mode", var_name="Metric", value_name="Score (%)"
    )

    # Plot
    plt.figure(figsize=(12, 7))
    ax = sns.barplot(
        data=df, x="Metric", y="Score (%)", hue="Mode", palette=["#d1d1d1", "#2c3e50"]
    )

    # Add value labels
    for p in ax.patches:
        if p.get_height() > 0:
            ax.annotate(
                f"{p.get_height():.1f}%",
                (p.get_x() + p.get_width() / 2.0, p.get_height()),
                ha="center",
                va="center",
                xytext=(0, 9),
                textcoords="offset points",
                fontweight="bold",
            )

    plt.title("Performance Comparison: Vanilla LLM vs RAG-NetTwin", fontsize=14, pad=20)
    plt.ylim(0, 115)
    plt.tight_layout()

    output_path = "results/performance_comparison.png"
    plt.savefig(output_path, dpi=300)
    print(f"✅ Performance chart saved to: {output_path}")


def generate_latency_plot(data):
    results = data.get("results", [])
    rag_data = [
        r["rag_nettwin"]
        for r in results
        if "rag_nettwin" in r and "latency" in r["rag_nettwin"]
    ]

    if not rag_data:
        return

    latencies = [d["latency"] for d in rag_data]

    plt.figure(figsize=(10, 5))
    sns.histplot(latencies, kde=True, color="#2c3e50")
    plt.title("Latency Distribution (RAG-NetTwin Generation)", fontsize=12)
    plt.xlabel("Latency per Device (seconds)")
    plt.ylabel("Frequency")

    output_path = "results/latency_distribution.png"
    plt.savefig(output_path, dpi=300)
    print(f"✅ Latency distribution saved to: {output_path}")


def generate_ablation_plot():
    """
    Generates a combined chart for Ablation Study (Recommendation 1).
    """
    modes = ["none", "flat", "tiered"]
    summary = []

    for mode in modes:
        filepath = f"results/paper_evaluation_{mode}_latest.json"
        if not os.path.exists(filepath):
            continue

        with open(filepath, "r") as f:
            data = json.load(f)

        results = data.get("results", [])
        mode_data = [
            r["rag_nettwin"]
            for r in results
            if "rag_nettwin" in r and r["rag_nettwin"].get("status") != "ERROR"
        ]

        if not mode_data:
            continue

        pass_count = sum(1 for d in mode_data if d.get("status") in ["PASS", "WARNING"])
        hal_count = sum(
            1
            for d in mode_data
            if any(h.get("is_hallucinated") for h in d.get("hallucinations", []))
        )
        cfr_count = sum(1 for d in mode_data if d.get("cfr_failure", False))
        functional_pass_count = sum(
            1 for d in mode_data if d.get("functional_status") == "PASS"
        )

        label_map = {
            "none": "No RAG",
            "flat": "Flat RAG",
            "tiered": "Tiered RAG (Ours)",
        }

        summary.append(
            {
                "Strategy": label_map[mode],
                "Syntactic Validity": (pass_count / len(mode_data)) * 100,
                "Functional Success": (functional_pass_count / len(mode_data)) * 100,
                "Hallucination-Free": ((len(mode_data) - hal_count) / len(mode_data))
                * 100,
                "CFR Faithfulness": ((len(mode_data) - cfr_count) / len(mode_data))
                * 100,
            }
        )

    if not summary:
        print("No ablation data found to plot.")
        return

    df = pd.DataFrame(summary).melt(
        id_vars="Strategy", var_name="Metric", value_name="Score (%)"
    )

    plt.figure(figsize=(14, 8))
    ax = sns.barplot(
        data=df, x="Metric", y="Score (%)", hue="Strategy", palette="viridis"
    )

    for p in ax.patches:
        if p.get_height() > 0:
            ax.annotate(
                f"{p.get_height():.1f}%",
                (p.get_x() + p.get_width() / 2.0, p.get_height()),
                ha="center",
                va="center",
                xytext=(0, 9),
                textcoords="offset points",
                fontweight="bold",
            )

    plt.title(
        "Ablation Study: Impact of Hierarchical RAG Strategy", fontsize=14, pad=20
    )
    plt.ylim(0, 115)
    plt.tight_layout()

    output_path = "results/ablation_study.png"
    plt.savefig(output_path, dpi=300)
    print(f"✅ Ablation Study chart saved to: {output_path}")


if __name__ == "__main__":
    data = load_data()
    if data:
        os.makedirs("results", exist_ok=True)
        generate_performance_plot(data)
        generate_latency_plot(data)

    # Also attempt ablation plot if files exist
    generate_ablation_plot()
