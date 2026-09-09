import pytest
from src.core.models import RetrievalResult
from src.retrieval.hybrid.fusion import Fusion


def _make_result(chunk_id: str, score: float, document_id: str = "d1", text: str = "text") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        score=score,
        retrieval_method="test",
    )


def test_rrf_single_list():
    dense = [_make_result("c1", 1.0), _make_result("c2", 0.8)]
    sparse = [_make_result("c2", 0.9), _make_result("c3", 0.5)]
    fused = Fusion.reciprocal_rank_fusion(dense, sparse, k=60)
    assert fused[0].chunk_id == "c2"
    assert abs(fused[0].score - (1 / 62 + 1 / 61)) < 1e-9


def test_rrf_multiple_queries():
    results_q1 = [_make_result("c1", 1.0)]
    results_q2 = [_make_result("c2", 1.0)]
    fused = Fusion.reciprocal_rank_fusion(results_q1, results_q2, k=60)
    ids = [r.chunk_id for r in fused]
    assert "c1" in ids
    assert "c2" in ids


def test_rrf_duplicate_across_queries():
    results_q1 = [_make_result("c1", 1.0)]
    results_q2 = [_make_result("c1", 0.9)]
    fused = Fusion.reciprocal_rank_fusion(results_q1, results_q2, k=60)
    top = fused[0]
    assert top.chunk_id == "c1"
    expected = 1 / 61 + 1 / 61
    assert abs(top.score - expected) < 1e-9


def test_weighted_fusion():
    dense = [_make_result("c1", 0.9), _make_result("c2", 0.5)]
    sparse = [_make_result("c1", 0.8), _make_result("c3", 0.7)]
    fused = Fusion.weighted_score_fusion(dense, sparse, alpha=0.7)
    ids = [r.chunk_id for r in fused]
    assert "c1" in ids
    assert "c2" in ids
    assert "c3" in ids


def test_weighted_fusion_alpha_1():
    dense = [_make_result("c1", 0.9)]
    sparse = [_make_result("c2", 0.8)]
    fused = Fusion.weighted_score_fusion(dense, sparse, alpha=1.0)
    assert fused[0].chunk_id == "c1"


def test_weighted_fusion_alpha_0():
    dense = [_make_result("c1", 0.9)]
    sparse = [_make_result("c2", 0.8)]
    fused = Fusion.weighted_score_fusion(dense, sparse, alpha=0.0)
    assert fused[0].chunk_id == "c2"


def test_rrf_empty():
    fused = Fusion.reciprocal_rank_fusion([], [], k=60)
    assert fused == []


def test_weighted_fusion_empty():
    fused = Fusion.weighted_score_fusion([], [], alpha=0.5)
    assert fused == []
