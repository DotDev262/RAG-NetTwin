#!/usr/bin/env python3
"""
Generate Figure 2: Chunking Sensitivity Analysis
Hallucination Rate vs. Chunk Size Strategy

Run this script to generate the figure for Section 5.2.1
Requires: pip install matplotlib numpy
"""

import matplotlib.pyplot as plt

# Data from Table III-a
strategies = [
    "Flat 100",
    "Tier 1\nOnly",
    "Flat 300",
    "Flat 500",
    "Tier 1+2",
    "Flat 1000",
    "Tiered\n(Ours)",
]

hr_values = [3.2, 2.8, 2.1, 1.8, 1.7, 1.6, 1.4]

# Colors - highlight Tiered (Ours) and Tier 1+2
colors = []
for s in strategies:
    if "Tiered" in s:
        colors.append("#2ca02c")  # Green for ours
    elif "Tier 1+2" in s:
        colors.append("#1f77b4")  # Blue for near-optimal
    else:
        colors.append("#d62728")  # Red for baseline

fig, ax = plt.subplots(figsize=(12, 7))

bars = ax.bar(
    strategies, hr_values, color=colors, edgecolor="black", linewidth=1.0, width=0.7
)

# Add value labels on bars
for bar, val in zip(bars, hr_values):
    height = bar.get_height()
    ax.annotate(
        f"{val:.1f}%",
        xy=(bar.get_x() + bar.get_width() / 2, height),
        xytext=(0, 3),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
    )

# Add baseline reference line
ax.axhline(y=1.4, color="#2ca02c", linestyle="--", alpha=0.3, linewidth=1)

# Styling
ax.set_ylabel("Hallucination Rate (%)", fontsize=14)
ax.set_xlabel("Chunking Strategy", fontsize=14)
ax.set_ylim(0, 4.5)
ax.set_xlim(-0.5, len(strategies) - 0.5)

# Legend
from matplotlib.patches import Patch  # noqa: E402

legend_elements = [
    Patch(
        facecolor="#2ca02c",
        edgecolor="black",
        label="Tiered Hierarchical (Ours) - Sweet Spot",
    ),
    Patch(facecolor="#1f77b4", edgecolor="black", label="Near-Optimal (Tier 1+2)"),
    Patch(facecolor="#d62728", edgecolor="black", label="Baseline Strategies"),
]
ax.legend(handles=legend_elements, loc="upper right", fontsize=10)

# Grid
ax.yaxis.grid(True, linestyle="--", alpha=0.5)
ax.set_axisbelow(True)

plt.tight_layout()
plt.savefig("figure_chunking_sensitivity.png", dpi=300, bbox_inches="tight")
plt.savefig("figure_chunking_sensitivity.pdf", bbox_inches="tight")
print(
    "Figure saved: figure_chunking_sensitivity.png and figure_chunking_sensitivity.pdf"
)
