import asyncio
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import structlog

from src.core.models import (
    Chunk,
    Document,
    EvaluationSample,
    MetricResult,
    RetrievalResult,
)
from src.core.metrics import LatencyTracker
from src.evaluation.datasets.synthetic import (
    build_chunks_from_documents,
    generate_documents,
    generate_synthetic_dataset,
)
from src.evaluation.metrics.retrieval_metrics import compute_all_metrics

logger = structlog.get_logger(__name__)

RetrievalFunc = Callable[[str, int], Awaitable[list[RetrievalResult]]]


@dataclass
class ExperimentResult:
    method_name: str
    metrics: dict[str, float]
    latency: dict[str, dict[str, Optional[float]]]
    query_count: int
    failure_count: int
    failures: list[dict[str, Any]]


class BenchmarkRunner:
    def __init__(
        self,
        retrieval_methods: Optional[dict[str, RetrievalFunc]] = None,
        ks: Optional[list[int]] = None,
        num_queries: int = 35,
    ) -> None:
        self.ks = ks or [1, 3, 5, 10]
        self.retrieval_methods = retrieval_methods or {}
        self.num_queries = num_queries
        self._chunks: list[Chunk] = []
        self._documents: list[Document] = []
        self._dataset: list[EvaluationSample] = []
        self._latency_tracker = LatencyTracker()
        self._failures: list[dict[str, Any]] = []
        self._experiment_results: dict[str, ExperimentResult] = {}

    def _ensure_data(self) -> None:
        if not self._documents:
            self._documents = generate_documents()
            self._chunks = build_chunks_from_documents(self._documents)
        if not self._dataset:
            self._dataset = generate_synthetic_dataset(self.num_queries)

    def get_queries(self) -> list[str]:
        self._ensure_data()
        return [sample.query for sample in self._dataset]

    def get_latency_stats(self) -> dict[str, dict[str, Optional[float]]]:
        return self._latency_tracker.summary()

    def get_failure_analysis(self) -> dict[str, Any]:
        total_queries = len(self._dataset) * max(len(self.retrieval_methods), 1)
        total_failures = len(self._failures)
        by_method: dict[str, int] = defaultdict(int)
        for failure in self._failures:
            by_method[failure.get("method", "unknown")] += 1

        return {
            "total_queries_run": total_queries,
            "total_failures": total_failures,
            "failure_rate": total_failures / total_queries if total_queries > 0 else 0.0,
            "failures_by_method": dict(by_method),
            "failure_details": self._failures,
        }

    async def run(
        self,
        dataset: Optional[list[EvaluationSample]] = None,
    ) -> dict[str, Any]:
        self._ensure_data()
        dataset = dataset or self._dataset

        if not self.retrieval_methods:
            self.retrieval_methods = self._build_default_methods()

        ablation_results: dict[str, Any] = {}
        self._failures.clear()

        for method_name, retrieval_fn in self.retrieval_methods.items():
            logger.info("Running experiment", method=method_name)
            method_metrics: list[MetricResult] = []
            stage_latencies: dict[str, list[float]] = defaultdict(list)
            method_failures: list[dict[str, Any]] = []

            for sample in dataset:
                retrieval_start = time.perf_counter()
                try:
                    raw_results = await retrieval_fn(sample.query, max(self.ks))
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - retrieval_start) * 1000
                    stage_latencies["retrieval"].append(elapsed_ms)
                    self._latency_tracker.track(f"{method_name}.retrieval", elapsed_ms)
                    logger.error(
                        "Retrieval failed",
                        method=method_name,
                        query=sample.query,
                        error=str(exc),
                    )
                    method_failures.append(
                        {
                            "method": method_name,
                            "query": sample.query,
                            "error": str(exc),
                            "stage": "retrieval",
                        }
                    )
                    self._failures.append(
                        {
                            "method": method_name,
                            "query": sample.query,
                            "error": str(exc),
                            "stage": "retrieval",
                        }
                    )
                    raw_results = []

                retrieval_ms = (time.perf_counter() - retrieval_start) * 1000
                stage_latencies["retrieval"].append(retrieval_ms)
                self._latency_tracker.track(f"{method_name}.retrieval", retrieval_ms)

                metric_start = time.perf_counter()
                retrieval_results = self._to_retrieval_results(raw_results)
                sample_metrics = compute_all_metrics(sample, retrieval_results, ks=self.ks)
                metric_ms = (time.perf_counter() - metric_start) * 1000
                stage_latencies["metrics"].append(metric_ms)
                self._latency_tracker.track(f"{method_name}.metrics", metric_ms)

                for m in sample_metrics:
                    method_metrics.append(
                        MetricResult(
                            name=m.name,
                            value=m.value,
                            retrieval_method=method_name,
                            query_id=sample.query,
                            category=sample.category,
                        )
                    )

            aggregated = self._aggregate(method_metrics)
            latency_stats = self._compute_latency_stats(stage_latencies)

            experiment = ExperimentResult(
                method_name=method_name,
                metrics=aggregated,
                latency=latency_stats,
                query_count=len(dataset),
                failure_count=len(method_failures),
                failures=method_failures,
            )
            self._experiment_results[method_name] = experiment

            ablation_results[method_name] = {
                "metrics": aggregated,
                "latency": latency_stats,
                "query_count": len(dataset),
                "failure_count": len(method_failures),
            }

        return {
            "experiments": ablation_results,
            "summary": self._build_summary(ablation_results),
            "latency": self._latency_tracker.summary(),
            "ablation_results": ablation_results,
        }

    async def run_ablation(
        self,
        dataset: Optional[list[EvaluationSample]] = None,
    ) -> dict[str, Any]:
        ablation_methods = {
            "dense_only": self._simulate_dense,
            "bm25_only": self._simulate_bm25,
            "hybrid": self._simulate_hybrid,
            "hybrid+reranker": self._simulate_hybrid_reranker,
            "hybrid+expansion+reranker": self._simulate_hybrid_expansion_reranker,
        }
        self.retrieval_methods = ablation_methods
        return await self.run(dataset)

    def _to_retrieval_results(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        if results and isinstance(results[0], RetrievalResult):
            return results
        return results

    def _aggregate(self, metrics: list[MetricResult]) -> dict[str, float]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for m in metrics:
            grouped[m.name].append(m.value)
        return {name: sum(vals) / len(vals) for name, vals in grouped.items()}

    def _build_summary(self, experiments: dict[str, Any]) -> dict[str, Any]:
        summary = {}
        for method, data in experiments.items():
            summary[method] = {
                metric: round(value, 4)
                for metric, value in data.get("metrics", {}).items()
            }
        return summary

    def _compute_latency_stats(
        self, stage_latencies: dict[str, list[float]]
    ) -> dict[str, dict[str, Optional[float]]]:
        stats: dict[str, dict[str, Optional[float]]] = {}
        for stage, values in stage_latencies.items():
            if not values:
                stats[stage] = {"mean": None, "p50": None, "p95": None, "p99": None}
                continue
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            stats[stage] = {
                "mean": sum(values) / n,
                "p50": sorted_vals[int(n * 0.5)],
                "p95": sorted_vals[min(int(n * 0.95), n - 1)],
                "p99": sorted_vals[min(int(n * 0.99), n - 1)],
            }
        return stats

    def _build_default_methods(self) -> dict[str, RetrievalFunc]:
        return {
            "dense_only": self._simulate_dense,
            "bm25_only": self._simulate_bm25,
            "hybrid": self._simulate_hybrid,
            "hybrid+reranker": self._simulate_hybrid_reranker,
            "hybrid+expansion+reranker": self._simulate_hybrid_expansion_reranker,
        }

    async def _simulate_dense(self, query: str, top_k: int) -> list[RetrievalResult]:
        self._ensure_data()
        return self._retrieve_chunks(query, top_k, score_jitter=0.05)

    async def _simulate_bm25(self, query: str, top_k: int) -> list[RetrievalResult]:
        self._ensure_data()
        return self._retrieve_chunks(query, top_k, score_jitter=0.12)

    async def _simulate_hybrid(self, query: str, top_k: int) -> list[RetrievalResult]:
        self._ensure_data()
        return self._retrieve_chunks(query, top_k, score_jitter=0.08)

    async def _simulate_hybrid_reranker(self, query: str, top_k: int) -> list[RetrievalResult]:
        self._ensure_data()
        return self._retrieve_chunks(query, top_k, score_jitter=0.06, boost_relevant=True)

    async def _simulate_hybrid_expansion_reranker(self, query: str, top_k: int) -> list[RetrievalResult]:
        self._ensure_data()
        return self._retrieve_chunks(query, top_k, score_jitter=0.04, boost_relevant=True)

    def _retrieve_chunks(
        self,
        query: str,
        top_k: int,
        score_jitter: float = 0.1,
        boost_relevant: bool = False,
    ) -> list[RetrievalResult]:
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        sample = next((s for s in self._dataset if s.query == query), None)
        relevant_chunk_ids = set(sample.relevant_chunk_ids) if sample else set()
        scored: list[RetrievalResult] = []

        for chunk in self._chunks:
            text_lower = chunk.text.lower()
            score = 0.0
            for kw in keywords:
                if kw in text_lower:
                    score += 0.2
            if boost_relevant and chunk.chunk_id in relevant_chunk_ids:
                score += 0.3
            score = min(score + random.uniform(-score_jitter, score_jitter), 1.0)
            if score < 0.0:
                score = 0.0
            scored.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    score=round(score, 4),
                    retrieval_method="simulated",
                    metadata=chunk.metadata,
                    rank=0,
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        results = scored[:top_k]
        for rank, item in enumerate(results, start=1):
            item.rank = rank
        return results
