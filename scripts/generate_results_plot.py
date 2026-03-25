import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from pathlib import Path

# Set professional style
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12, 'font.family': 'sans-serif'})

# Data from Paper Evaluation (Phase 1)
metrics = ['Syntactic Validity', 'Hallucination-Free', 'Semantic Faithfulness']
vanilla_scores = [64.0, 95.7, 52.0]  # Baselines from PDF/Research context
rag_nettwin_scores = [87.0, 100.0, 82.6] # Actual latest results

x = np.arange(len(metrics))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))

# Create bars
rects1 = ax.bar(x - width/2, vanilla_scores, width, label='Vanilla LLM (Baseline)', color='#d1d1d1', edgecolor='black', alpha=0.8)
rects2 = ax.bar(x + width/2, rag_nettwin_scores, width, label='RAG-NetTwin (Proposed)', color='#2c3e50', edgecolor='black')

# Add labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Score (%)')
ax.set_title('Phase 1 Performance Comparison: RAG-NetTwin vs. Vanilla LLM', pad=20, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(metrics)
ax.set_ylim(0, 115) # Room for labels
ax.legend(loc='upper left', frameon=True)

# Add value labels on top of bars
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}%',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')

autolabel(rects1)
autolabel(rects2)

# Add a footnote/insight
plt.figtext(0.5, 0.01, "N=23 Intents (OSPF, BGP, ACL). RAG-NetTwin eliminates hallucinations and significantly boosts reliability.", 
            ha="center", fontsize=10, bbox={"facecolor":"orange", "alpha":0.1, "pad":5})

fig.tight_layout()

# Save the plot
output_path = Path("results/performance_comparison.png")
plt.savefig(output_path, dpi=300)
print(f"Graph saved successfully to: {output_path}")
