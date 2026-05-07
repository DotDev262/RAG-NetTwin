from typing import List
import numpy as np


def calculate_mrr(relevant_id: str, retrieved_ids: List[str]) -> float:
    """
    Calculates Mean Reciprocal Rank (MRR).
    """
    try:
        rank = retrieved_ids.index(relevant_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def calculate_ndcg(relevant_id: str, retrieved_ids: List[str]) -> float:
    """
    Calculates Normalized Discounted Cumulative Gain (NDCG) for a single relevant item.
    """
    try:
        rank = retrieved_ids.index(relevant_id) + 1
        dcg = 1.0 / np.log2(rank + 1)
        idcg = 1.0
        return dcg / idcg
    except ValueError:
        return 0.0
