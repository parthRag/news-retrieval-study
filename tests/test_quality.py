import pytest

from news_ir.quality import filter_candidates, quality_scores


def test_symmetric_filter_preserves_order_and_exact_first_occurrence():
    articles = {"a": {"text": "body", "contents_sha256": "x"},
                "b": {"text": "body", "contents_sha256": "x"},
                "c": {"text": " \n", "contents_sha256": "y"},
                "d": {"text": "different", "contents_sha256": "z"}}
    assert filter_candidates(list(articles), articles, empty=True, deduplicate=True) == ["a", "d"]
    assert filter_candidates(list(articles), articles, deduplicate=True) == ["a", "c", "d"]
    assert filter_candidates(list(articles), articles) == list(articles)


def test_content_metric_retains_duplicate_ranks_and_independent_ideal():
    a = {"a": {"contents_sha256": "x"}, "b": {"contents_sha256": "x"}, "c": {"contents_sha256": "z"}}
    labels = {"a": 2, "b": 2, "c": 1}
    raw = quality_scores(["a", "b", "c"], a, labels)
    dedup = quality_scores(["a", "c"], a, labels)
    assert raw["fixed_reference_ndcg_at_5"] == 1
    assert dedup["fixed_reference_ndcg_at_5"] < 1
    assert raw["unique_content_ndcg_at_5"] < dedup["unique_content_ndcg_at_5"] == 1
    assert dedup["precision_at_5"] == .4  # Missing results cannot improve the denominator.
    assert quality_scores([], a, labels)["unique_content_ndcg_at_5"] == 0
    with pytest.raises(ValueError, match="conflicting"):
        quality_scores(["a"], a, {"a": 2, "b": 0})
    with pytest.raises(ValueError, match="judged"):
        quality_scores(["absent"], a, labels)
