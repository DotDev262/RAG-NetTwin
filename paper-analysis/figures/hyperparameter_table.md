
**Table VI: Hyperparameter Selection and Justification**

| Hyperparameter | Values Tested | Selected Value | Justification |
|:--------------|:-------------|:-------------:|:-------------|
| **Community Budget** | 5, 10, 15, 20, 30 | **15** | Balances token budget (3,500 target) with precision/recall trade-off. Budget=15 yields ~3,000 tokens total context with ~90% precision. |
| **Cosine Threshold** | 0.45, 0.55, 0.65, 0.70, 0.75 | **0.70** | At 0.70, the system correctly triggers expansion for difficult queries while avoiding unnecessary expansion for straightforward intents. Lower values (0.55) cause over-expansion; higher values (0.75) miss relevant context. |
| **God Node Pruning** | Degree ≥ threshold | **Dynamic** (max(avg×5, p99)) | Prevents hub nodes (>50 connections typically) from dominating context. Dynamic threshold adapts to graph topology. |
| **Pilot Search K** | 5, 10, 20 | **10** | k=10 provides sufficient initial context without overwhelming the LLM. k=5 may miss relevant chunks; k=20 increases noise. |
| **Chunk Size** | 300, 500, 800, 1000 | **Tiered** | Tier 1: 50-150 tokens (commands), Tier 2: 300-500 tokens (context), Tier 3: 1000-2000 tokens (examples). Hierarchical chunking preserves command-parameter relationships. |

**Key Observations from Ablation:**

1. **Community Budget = 15** provides optimal balance:
   - Token budget: ~3,000 tokens (within 3,500 target)
   - Precision: ~90% (high relevance)
   - Recall: ~85% (good coverage)

2. **Cosine Threshold = 0.70**:
   - At threshold < 0.65: Over-expansion leads to semantic drift
   - At threshold > 0.75: Under-expansion misses relevant context
   - 0.70 represents the precision-recall crossover point

3. **Dynamic God Node Pruning**:
   - Fixed threshold (e.g., degree > 50) fails for graphs with non-uniform degree distribution
   - Dynamic threshold (avg×5 or percentile-99) adapts to graph structure
