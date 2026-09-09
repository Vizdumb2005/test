import math
from typing import Any

from src.core.models import EvaluationSample, MetricResult, RetrievalResult


def precision_at_k(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    k: int,
) -> float:
    top_k = results[:k]
    if not top_k:
        return 0.0
    relevant = {cid for cid in sample.relevant_chunk_ids}
    hits = sum(1 for r in top_k if r.chunk_id in relevant)
    return hits / k


def recall_at_k(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    k: int,
) -> float:
    if not sample.relevant_chunk_ids:
        return 0.0
    top_k = results[:k]
    relevant = set(sample.relevant_chunk_ids)
    hits = sum(1 for r in top_k if r.chunk_id in relevant)
    return hits / len(relevant)


def f1_at_k(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    k: int,
) -> float:
    p = precision_at_k(sample, results, k)
    r = recall_at_k(sample, results, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def mrr(sample: EvaluationSample, results: list[RetrievalResult]) -> float:
    relevant = set(sample.relevant_chunk_ids)
    for rank, result in enumerate(results, start=1):
        if result.chunk_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    k: int,
) -> float:
    top_k = results[:k]
    relevant = set(sample.relevant_chunk_ids)

    dcg = 0.0
    for rank, result in enumerate(top_k, start=1):
        rel = 1.0 if result.chunk_id in relevant else 0.0
        dcg += rel / math.log2(rank + 1)

    ideal_hits = min(len(relevant), k)
    idcg = 0.0
    for rank in range(1, ideal_hits + 1):
        idcg += 1.0 / math.log2(rank + 1)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def hit_rate_at_k(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    k: int,
) -> float:
    top_k = results[:k]
    relevant = set(sample.relevant_chunk_ids)
    return 1.0 if any(r.chunk_id in relevant for r in top_k) else 0.0


def compute_all_metrics(
    sample: EvaluationSample,
    results: list[RetrievalResult],
    ks: list[int] | None = None,
) -> list[MetricResult]:
    ks = ks or [1, 3, 5, 10]
    metrics: list[MetricResult] = []
    for k in ks:
        if k == 0:
            continue
        metrics.append(
            MetricResult(
                name=f"precision@{k}",
                value=precision_at_k(sample, results, k),
                retrieval_method="",
                query_id=sample.query,
                category=sample.category,
            )
        )
        metrics.append(
            MetricResult(
                name=f"recall@{k}",
                value=recall_at_k(sample, results, k),
                retrieval_method="",
                query_id=sample.query,
                category=sample.category,
            )
        )
        metrics.append(
            MetricResult(
                name=f"f1@{k}",
                value=f1_at_k(sample, results, k),
                retrieval_method="",
                query_id=sample.query,
                category=sample.category,
            )
        )
        metrics.append(
            MetricResult(
                name=f"ndcg@{k}",
                value=ndcg_at_k(sample, results, k),
                retrieval_method="",
                query_id=sample.query,
                category=sample.category,
            )
        )
        metrics.append(
            MetricResult(
                name=f"hit_rate@{k}",
                value=hit_rate_at_k(sample, results, k),
                retrieval_method="",
                query_id=sample.query,
                category=sample.category,
            )
        )

    metrics.append(
        MetricResult(
            name="mrr",
            value=mrr(sample, results),
            retrieval_method="",
            query_id=sample.query,
            category=sample.category,
        )
    )
    return metrics
