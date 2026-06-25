"""
Generate all figures for RAG-NetTwin IEEE Access Paper
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import seaborn as sns
from pathlib import Path

sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "font.size": 14,
    "font.family": "serif",
    "axes.labelsize": 14,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "legend.fontsize": 13,
})

OUTPUT_DIR = Path("paper-analysis/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def save_fig(fig, name):
    path = OUTPUT_DIR / f"{name}.jpg"
    fig.savefig(path, dpi=300, bbox_inches="tight", format="jpg")
    print(f"  Saved: {path}")
    plt.close(fig)


def figure_2_main_results():
    """Fig. 2: Main Results Bar Chart - Vanilla LLM vs RAG-NetTwin"""
    fig, ax = plt.subplots(figsize=(9, 4.5))

    metrics = ["Strict SV", "PEA", "GNS3 CAR", "Hallucination-Free"]
    vanilla = [74.3, 80.0, 0.0, 74.3]  # Hallucination-free = 100 - HR
    rag_nettwin = [94.3, 100.0, 93.5, 97.1]

    x = np.arange(len(metrics))
    width = 0.35

    bars1 = ax.bar(x - width/2, vanilla, width, label="Vanilla LLM", color="#d1d1d1", edgecolor="black")
    bars2 = ax.bar(x + width/2, rag_nettwin, width, label="RAG-NetTwin", color="#2c3e50", edgecolor="black")

    for bar in bars1 + bars2:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f"{height:.1f}%",
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords="offset points",
                       ha="center", va="bottom", fontsize=13, fontweight="bold")

    ax.set_ylabel("Score (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 115)
    ax.legend(loc="upper left")
    ax.axhline(y=100, color="gray", linestyle="--", alpha=0.3)

    save_fig(fig, "figure_2_main_results")


def figure_3_ablation():
    """Fig. 3: Ablation Study - Incremental contribution of each component"""
    fig, ax = plt.subplots(figsize=(10, 4.5))

    configs = [
        "Vanilla LLM",
        "+ Flat RAG",
        "+ Version Filter",
        "+ GraphRAG",
        "+ Hallucination\nRefinement"
    ]
    sv = [74.3, 82.1, 86.8, 91.3, 94.3]
    hr = [25.7, 12.4, 8.7, 4.2, 2.9]  # Inverted for display
    car = [0.0, 52.3, 64.1, 79.6, 93.5]

    x = np.arange(len(configs))
    width = 0.25

    bars1 = ax.bar(x - width, sv, width, label="Strict SV", color="#3498db", edgecolor="black")
    bars2 = ax.bar(x, car, width, label="GNS3 CAR", color="#27ae60", edgecolor="black")
    bars3 = ax.bar(x + width, [100-h for h in hr], width, label="Hallucination-Free", color="#e74c3c", edgecolor="black")

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f"{height:.1f}%",
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 2), textcoords="offset points",
                            ha="center", va="bottom", fontsize=12)

    ax.set_ylabel("Score (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=15, ha="right")
    ax.set_ylim(0, 115)
    ax.legend(loc="upper left", ncol=3)

    save_fig(fig, "figure_3_ablation")


def figure_4_retrieval():
    """Fig. 4: Retrieval Performance - GraphRAG vs Baseline"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.5))

    methods = ["Baseline RAG", "GraphRAG"]
    precision = [0.2764, 0.4856]
    recall = [10, 135]
    tokens = [57533, 3503]

    # Left: Precision comparison
    bars1 = ax1.bar(methods, precision, color=["#95a5a6", "#2c3e50"], edgecolor="black", width=0.5)
    ax1.set_ylabel("Mean Semantic Precision")
    ax1.set_ylim(0, 0.6)
    for bar in bars1:
        height = bar.get_height()
        ax1.annotate(f"{height:.4f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                     ha="center", va="bottom", fontsize=12, fontweight="bold")

    # Right: Token reduction (log scale)
    bars2 = ax2.bar(methods, tokens, color=["#95a5a6", "#2c3e50"], edgecolor="black", width=0.5)
    ax2.set_ylabel("Tokens per Query (log scale)")
    ax2.set_yscale("log")
    for bar in bars2:
        height = bar.get_height()
        ax2.annotate(f"~{height:,}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=12, fontweight="bold")

    save_fig(fig, "figure_4_retrieval")


def figure_5_semantic_gap():
    """Fig. 5: Semantic Gap Analysis - ISR vs CAR breakdown"""
    fig, ax = plt.subplots(figsize=(9, 4.5))

    categories = ["Vanilla\nLLM", "Flat\nRAG", "Version\nFilter", "GraphRAG", "RAG-NetTwin\n(Full)"]
    isr = [0, 65, 78, 92, 100]
    car = [0, 45, 58, 72, 93.5]

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width/2, isr, width, label="GNS3 ISR (Recognition)", color="#3498db", edgecolor="black")
    bars2 = ax.bar(x + width/2, car, width, label="GNS3 CAR (Correctness)", color="#27ae60", edgecolor="black")

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f"{height:.1f}%",
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 2), textcoords="offset points",
                            ha="center", va="bottom", fontsize=13, fontweight="bold")

    ax.set_ylabel("Percentage (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 120)
    ax.legend(loc="upper left")

    # Add gap annotation
    ax.annotate("Semantic\nGap: 6.5%", xy=(4.175, 96.75), xytext=(3.5, 80),
                fontsize=13, ha="center",
                arrowprops=dict(arrowstyle="->", color="red", lw=1.5),
                color="red", fontweight="bold")

    save_fig(fig, "figure_5_semantic_gap")


def figure_6_knowledge_graph():
    """Fig. 6: Simplified Knowledge Graph Structure Visualization"""
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_xlim(-2, 12)
    ax.set_ylim(-1, 10)
    ax.set_aspect("equal")
    ax.axis("off")

    # Community nodes
    communities = {
        "router-ospf": (2, 7, "#3498db"),
        "router-bgp": (5, 7, "#e74c3c"),
        "acl-extended": (8, 7, "#27ae60"),
        "interface": (2, 4, "#9b59b6"),
        "vlan": (5, 4, "#f39c12"),
    }

    for name, (cx, cy, color) in communities.items():
        circle = plt.Circle((cx, cy), 0.8, color=color, alpha=0.7, ec="black", lw=1.5)
        ax.add_patch(circle)
        ax.text(cx, cy, name.replace("-", "\n"), ha="center", va="center", fontsize=11, fontweight="bold", color="white")

    # God Node (pruned)
    ax.text(0.5, 9.5, "God Nodes\n(pruned)", ha="center", va="center", fontsize=13, style="italic", color="gray")
    ax.annotate("", xy=(2, 7.8), xytext=(1, 9.2), arrowprops=dict(arrowstyle="-", color="gray", lw=1, linestyle="dashed"))

    # Example CLI nodes connected to OSPF community
    ospf_commands = [
        (0, 5.5, "network <ip> area <id>"),
        (1, 4.8, "area <id> authentication"),
        (3, 5.5, "passive-interface <if>"),
        (4, 4.8, "redistribute ospf"),
    ]
    for (cx, cy, text) in ospf_commands:
        rect = plt.Rectangle((cx-0.6, cy-0.25), 1.2, 0.5, color="#ecf0f1", ec="#2c3e50", lw=1)
        ax.add_patch(rect)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=11)

    # Connections from community to commands
    for (cx, cy, _) in ospf_commands:
        ax.plot([2, cx], [6.3, cy+0.25], "k-", lw=0.5, alpha=0.4)

    # Documentation node
    doc_rect = plt.Rectangle((8, 4.5), 2.5, 1.2, color="#f8f9fa", ec="#2c3e50", lw=1.5)
    ax.add_patch(doc_rect)
    ax.text(9.25, 5.1, "Documentation\nNodes\n(OS Version Tagged)", ha="center", va="center", fontsize=12)
    ax.annotate("", xy=(8, 6.8), xytext=(8.8, 5.7), arrowprops=dict(arrowstyle="->", color="#2c3e50", lw=1))

    # Stats box
    stats_text = "Graph Statistics:\n• 1,334 Nodes\n• 162 Communities\n• 13.5 avg degree\n• God Node Pruning: >50"
    ax.text(10, 2, stats_text, fontsize=13, va="top", ha="left",
            bbox=dict(boxstyle="round", facecolor="#ecf0f1", edgecolor="#bdc3c7"))

    # Multi-query expansion illustration
    ax.annotate("", xy=(5, 8.5), xytext=(2, 8), arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=1.5))
    ax.text(3.5, 8.8, "Multi-Query\nExpansion", fontsize=12, ha="center", color="#e74c3c")

    save_fig(fig, "figure_6_knowledge_graph")


def figure_token_comparison():
    """Additional: Token reduction visualization"""
    fig, ax = plt.subplots(figsize=(7, 4))

    categories = ["Baseline RAG", "GraphRAG"]
    values = [57533, 3503]
    colors = ["#e74c3c", "#27ae60"]

    bars = ax.barh(categories, values, color=colors, edgecolor="black", height=0.5)

    for bar, val in zip(bars, values):
        ax.text(val + 500, bar.get_y() + bar.get_height()/2, f"~{val:,} tokens",
               va="center", fontsize=12, fontweight="bold")

    ax.set_xlabel("Tokens per Query")
    ax.set_xlim(0, 65000)

    ax.annotate("", xy=(3503, 1), xytext=(57533, 1),
               arrowprops=dict(arrowstyle="<->", color="blue", lw=2))
    ax.text(30518, 1.25, "16.4x\nReduction", ha="center", fontsize=11, fontweight="bold", color="blue")

    save_fig(fig, "figure_token_reduction")


def main():
    print("Generating figures for RAG-NetTwin paper...")
    print("-" * 50)

    print("\n[1/6] Figure 2: Main Results...")
    figure_2_main_results()

    print("\n[2/6] Figure 3: Ablation Study...")
    figure_3_ablation()

    print("\n[3/6] Figure 4: Retrieval Performance...")
    figure_4_retrieval()

    print("\n[4/6] Figure 5: Semantic Gap...")
    figure_5_semantic_gap()

    print("\n[5/6] Figure 6: Knowledge Graph Structure...")
    figure_6_knowledge_graph()

    print("\n[6/6] Additional: Token Reduction...")
    figure_token_comparison()

    print("\n" + "-" * 50)
    print(f"All figures saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()