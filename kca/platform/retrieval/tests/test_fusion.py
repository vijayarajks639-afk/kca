"""WP-06: reciprocal-rank fusion of the lexical and vector orderings — pure."""

from kca.platform.retrieval.fusion import reciprocal_rank_fusion


def test_item_ranked_high_in_both_lists_wins() -> None:
    lexical = ["a", "b", "c"]
    vector = ["b", "c", "a"]
    fused = reciprocal_rank_fusion([lexical, vector])
    ranked = sorted(fused, key=lambda i: fused[i], reverse=True)
    assert ranked[0] == "b"  # rank 2 + rank 1 beats a (1+3) and c (3+2)


def test_item_present_in_only_one_list_still_scored() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["a"]])
    assert set(fused) == {"a", "b"}
    assert fused["a"] > fused["b"]  # a appears in both, b in one


def test_empty_rankings_return_empty() -> None:
    assert reciprocal_rank_fusion([[], []]) == {}


def test_higher_rank_beats_lower_rank_same_list() -> None:
    fused = reciprocal_rank_fusion([["first", "second", "third"]])
    assert fused["first"] > fused["second"] > fused["third"]
