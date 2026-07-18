"""WP-06: deterministic local embedding — pure, no I/O, no cloud SDK (rule 6).

A hashing bag-of-tokens embedding: good enough to demonstrate vector fusion,
fully offline and reproducible. Not semantically strong — that is honest and
intentional for a synthetic demo.
"""

import math

from kca.platform.retrieval.embedding import EMBEDDING_DIM, embed


def test_embedding_has_fixed_dimension() -> None:
    assert len(embed("collateral haircut policy")) == EMBEDDING_DIM


def test_embedding_is_deterministic() -> None:
    assert embed("loan to value threshold") == embed("loan to value threshold")


def test_embedding_is_l2_normalised() -> None:
    vec = embed("exposure at default")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-9


def test_different_text_gives_different_vectors() -> None:
    assert embed("collateral haircut") != embed("probability of default")


def test_empty_text_is_zero_vector() -> None:
    vec = embed("   ")
    assert vec == [0.0] * EMBEDDING_DIM


def test_token_order_does_not_matter_bag_of_words() -> None:
    assert embed("haircut collateral") == embed("collateral haircut")
