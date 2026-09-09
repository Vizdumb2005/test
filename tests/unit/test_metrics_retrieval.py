import pytest
from src.evaluation.metrics.retrieval_metrics import (
    precision_at_k,
    recall_at_k,
    f1_at_k,
    mrr,
    ndcg_at_k,
    hit_rate_at_k,
)
from src.core.models import EvaluationSample, RetrievalResult


def _make_result(chunk_id: str, score: float = 1.0) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=chunk_id,
        text=f"text for {chunk_id}",
        score=score,
        retrieval_method="test",
    )


def test_precision_at_k_perfect():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1", "c2", "c3"])
    results = [_make_result("c1"), _make_result("c2"), _make_result("c3"), _make_result("c4")]
    assert precision_at_k(sample, results, k=3) == 1.0


def test_precision_at_k_partial():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c1"), _make_result("c4"), _make_result("c5"), _make_result("c6")]
    assert precision_at_k(sample, results, k=2) == 0.5


def test_precision_at_k_zero():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c4"), _make_result("c5"), _make_result("c6")]
    assert precision_at_k(sample, results, k=3) == 0.0


def test_precision_at_k_k_greater_than_retrieved():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c1")]
    assert precision_at_k(sample, results, k=5) == 0.2


def test_recall_at_k_perfect():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1", "c2", "c3", "c4"])
    results = [_make_result("c1"), _make_result("c2"), _make_result("c3")]
    assert recall_at_k(sample, results, k=3) == 0.75


def test_recall_at_k_zero():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1", "c2"])
    results = [_make_result("c5"), _make_result("c6")]
    assert recall_at_k(sample, results, k=2) == 0.0


def test_recall_at_k_no_relevant():
    sample = EvaluationSample(query="q", relevant_chunk_ids=[])
    results = [_make_result("c1"), _make_result("c2")]
    assert recall_at_k(sample, results, k=2) == 0.0


def test_f1_at_k():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1", "c2"])
    results = [_make_result("c1"), _make_result("c4")]
    assert abs(f1_at_k(sample, results, k=2) - 0.5) < 1e-9


def test_f1_at_k_zero_denominator():
    sample = EvaluationSample(query="q", relevant_chunk_ids=[])
    results = [_make_result("c5")]
    assert f1_at_k(sample, results, k=1) == 0.0


def test_mrr_perfect():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c2"), _make_result("c1"), _make_result("c3")]
    assert mrr(sample, results) == 1/2


def test_mrr_no_relevant():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c4"), _make_result("c5")]
    assert mrr(sample, results) == 0.0


def test_mrr_first_rank():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c1"), _make_result("c2"), _make_result("c3")]
    assert mrr(sample, results) == 1.0


def test_ndcg_perfect():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1", "c2", "c3"])
    results = [_make_result("c1"), _make_result("c2"), _make_result("c3")]
    assert abs(ndcg_at_k(sample, results, k=3) - 1.0) < 1e-9


def test_ndcg_empty():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = []
    assert ndcg_at_k(sample, results, k=3) == 0.0


def test_ndcg_partial():
    import math
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    results = [_make_result("c4"), _make_result("c1"), _make_result("c5")]
    expected = 1.0 / math.log2(3)
    assert abs(ndcg_at_k(sample, results, k=3) - expected) < 1e-9


def test_hit_rate_hit():
    sample1 = EvaluationSample(query="q1", relevant_chunk_ids=["c1"])
    results1 = [_make_result("c1"), _make_result("c2")]
    sample2 = EvaluationSample(query="q2", relevant_chunk_ids=["c3"])
    results2 = [_make_result("c3"), _make_result("c4")]
    assert hit_rate_at_k(sample1, results1, k=2) == 1.0
    assert hit_rate_at_k(sample2, results2, k=2) == 1.0


def test_hit_rate_miss():
    sample1 = EvaluationSample(query="q1", relevant_chunk_ids=["c5"])
    results1 = [_make_result("c1"), _make_result("c2")]
    sample2 = EvaluationSample(query="q2", relevant_chunk_ids=["c6"])
    results2 = [_make_result("c3"), _make_result("c4")]
    assert hit_rate_at_k(sample1, results1, k=2) == 0.0
    assert hit_rate_at_k(sample2, results2, k=2) == 0.0


def test_hit_rate_partial():
    sample1 = EvaluationSample(query="q1", relevant_chunk_ids=["c1"])
    results1 = [_make_result("c1"), _make_result("c2")]
    sample2 = EvaluationSample(query="q2", relevant_chunk_ids=["c6"])
    results2 = [_make_result("c3"), _make_result("c4")]
    assert hit_rate_at_k(sample1, results1, k=2) == 1.0
    assert hit_rate_at_k(sample2, results2, k=2) == 0.0


def test_hit_rate_no_queries():
    sample = EvaluationSample(query="q", relevant_chunk_ids=["c1"])
    assert hit_rate_at_k(sample, [], k=2) == 0.0
