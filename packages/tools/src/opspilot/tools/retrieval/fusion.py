from __future__ import annotations

from typing import Literal


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def merge_sources(
    vector_ids: set[str],
    lexical_ids: set[str],
) -> dict[str, Literal["vector", "lexical", "both"]]:
    merged: dict[str, Literal["vector", "lexical", "both"]] = {}
    for item_id in vector_ids | lexical_ids:
        in_vector = item_id in vector_ids
        in_lexical = item_id in lexical_ids
        if in_vector and in_lexical:
            merged[item_id] = "both"
        elif in_vector:
            merged[item_id] = "vector"
        else:
            merged[item_id] = "lexical"
    return merged
