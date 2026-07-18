"""Reciprocal-rank fusion of the lexical and vector orderings.

RRF is rank-based, so it fuses the two signals without having to normalise a
ts_rank score against a cosine distance. score(id) = Σ 1/(k + rank) over each
ranking the id appears in (rank is 1-based). Higher is better.
"""

from collections.abc import Sequence

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores
