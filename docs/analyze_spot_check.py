#!/usr/bin/env python3
"""
Spot-Check Data Analyzer for RAG-NetTwin
Run this after completing the spot-check study to generate results for Section 5.8
"""

import csv
from collections import defaultdict
import statistics


def analyze_spot_check(csv_file: str) -> dict:
    """Analyze spot-check data and return results dict."""

    data = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)

    # Separate by condition
    with_trail = [r for r in data if r["condition"] == "with_trail"]
    without_trail = [r for r in data if r["condition"] == "without_trail"]

    # Calculate metrics
    def calc_metrics(rows):
        times = [
            float(r["verification_time_seconds"])
            for r in rows
            if r["verification_time_seconds"]
        ]
        correct = sum(1 for r in rows if r["answer"] == "CORRECT")
        confidence = [
            float(r["confidence_rating"]) for r in rows if r["confidence_rating"]
        ]

        return {
            "n": len(rows),
            "mean_time": statistics.mean(times) if times else 0,
            "std_time": statistics.stdev(times) if len(times) > 1 else 0,
            "accuracy": (correct / len(rows)) * 100 if rows else 0,
            "mean_confidence": statistics.mean(confidence) if confidence else 0,
            "std_confidence": statistics.stdev(confidence)
            if len(confidence) > 1
            else 0,
        }

    metrics_with = calc_metrics(with_trail)
    metrics_without = calc_metrics(without_trail)

    # Calculate deltas
    time_delta = (
        (metrics_without["mean_time"] - metrics_with["mean_time"])
        / metrics_without["mean_time"]
    ) * 100
    accuracy_delta = metrics_with["accuracy"] - metrics_without["accuracy"]
    confidence_delta = (
        metrics_with["mean_confidence"] - metrics_without["mean_confidence"]
    )

    return {
        "with_trail": metrics_with,
        "without_trail": metrics_without,
        "time_delta_pct": time_delta,
        "accuracy_delta": accuracy_delta,
        "confidence_delta": confidence_delta,
    }


def generate_paper_table(results: dict) -> str:
    """Generate LaTeX table for Section 5.8."""

    wt = results["with_trail"]
    wot = results["without_trail"]

    table = f"""| Metric | Without Audit Trail | With Audit Trail | Δ | 
|:-------|:-------------------:|:----------------:|:---:|
| **Mean Verification Time (s)** | {wot["mean_time"]:.0f} ± {wot["std_time"]:.0f} | **{wt["mean_time"]:.0f} ± {wt["std_time"]:.0f}** | **{results["time_delta_pct"]:.0f}%** |
| **Accuracy (%)** | {wot["accuracy"]:.1f}% | **{wt["accuracy"]:.1f}%** | **+{results["accuracy_delta"]:.1f}%** |
| **Mean Confidence (1-5)** | {wot["mean_confidence"]:.1f} ± {wot["std_confidence"]:.1f} | **{wt["mean_confidence"]:.1f} ± {wt["std_confidence"]:.1f}** | **+{results["confidence_delta"]:.1f}** |
"""
    return table


def main():
    print("RAG-NetTwin Spot-Check Analyzer")
    print("=" * 40)
    print()

    # Try to load data
    try:
        results = analyze_spot_check("SPOT_CHECK_DATA.csv")
    except FileNotFoundError:
        print("ERROR: SPOT_CHECK_DATA.csv not found.")
        print("Place your completed CSV in the same directory as this script.")
        print()
        print("Expected format:")
        print(
            "  participant_id,config_id,condition,verification_time_seconds,answer,confidence_rating,notes"
        )
        print()
        print("Conditions: 'with_trail' or 'without_trail'")
        return

    # Print results
    print("RESULTS SUMMARY")
    print("-" * 40)
    print()
    print(f"Without Audit Trail:")
    print(
        f"  - Mean Time: {results['without_trail']['mean_time']:.1f}s ± {results['without_trail']['std_time']:.1f}"
    )
    print(f"  - Accuracy: {results['without_trail']['accuracy']:.1f}%")
    print(f"  - Confidence: {results['without_trail']['mean_confidence']:.2f}")
    print()
    print(f"With Audit Trail:")
    print(
        f"  - Mean Time: {results['with_trail']['mean_time']:.1f}s ± {results['with_trail']['std_time']:.1f}"
    )
    print(f"  - Accuracy: {results['with_trail']['accuracy']:.1f}%")
    print(f"  - Confidence: {results['with_trail']['mean_confidence']:.2f}")
    print()
    print("DELTAS")
    print("-" * 40)
    print(f"Time Reduction: {results['time_delta_pct']:.1f}%")
    print(f"Accuracy Improvement: +{results['accuracy_delta']:.1f}%")
    print(f"Confidence Improvement: +{results['confidence_delta']:.2f}")
    print()
    print("=" * 40)
    print("PASTE THIS INTO SECTION 5.8:")
    print("=" * 40)
    print(generate_paper_table(results))


if __name__ == "__main__":
    main()
