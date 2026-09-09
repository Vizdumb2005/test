import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import structlog

from src.core.config import settings
from src.core.models import Chunk, Document
from src.evaluation.datasets.synthetic import (
    build_chunks_from_documents,
    generate_documents,
    generate_synthetic_dataset,
)
from src.evaluation.reports.generator import ReportGenerator
from src.evaluation.runners.benchmark_runner import BenchmarkRunner
from src.retrieval.dense.embedding_service import EmbeddingService
from src.retrieval.dense.qdrant_service import QdrantService
from src.retrieval.hybrid.fusion import HybridRetriever
from src.retrieval.sparse.bm25_retriever import BM25Retriever

logger = structlog.get_logger(__name__)


def _resolve_device(device: Optional[str]) -> str:
    if device:
        return device
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _build_retrieval_methods(
    chunks: list[Chunk],
    device: str,
    rebuild_index: bool,
    warmup_runs: int = 5,
) -> dict[str, Any]:
    embedding_service = EmbeddingService(device=device)
    qdrant_service = QdrantService(recreate=rebuild_index)
    bm25_retriever = BM25Retriever()

    document_texts = [chunk.text for chunk in chunks]
    chunk_ids = [chunk.chunk_id for chunk in chunks]

    bm25_path = Path("data/bm25_index.pkl")
    if rebuild_index or not bm25_path.exists():
        logger.info("Building BM25 index", doc_count=len(document_texts))
        bm25_retriever.index_documents(document_texts, chunk_ids)
        bm25_retriever.save(str(bm25_path))
    else:
        logger.info("Loading BM25 index", path=str(bm25_path))
        bm25_retriever.load(str(bm25_path))

    hybrid_retriever = HybridRetriever(
        embedding_service=embedding_service,
        qdrant_service=qdrant_service,
        bm25_retriever=bm25_retriever,
    )

    logger.info("Indexing documents into Qdrant", doc_count=len(chunks))
    vectors = embedding_service.embed_texts(document_texts).tolist()
    points = []
    for chunk, vector in zip(chunks, vectors):
        points.append(
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "vector": vector,
                "source": chunk.source,
                "file_name": chunk.file_name,
                "chunk_index": chunk.chunk_index,
                "document_type": chunk.document_type,
                "metadata": chunk.metadata,
            }
        )
    qdrant_service.upsert(points)
    logger.info("Qdrant indexing complete", point_count=len(points))

    logger.info("Pre-warming embedding model")
    _ = embedding_service.embed_query("warmup query for benchmark")

    async def dense_only(query: str, top_k: int) -> list[Any]:
        return await _retrieve_dense(hybrid_retriever, query, top_k)

    async def bm25_only(query: str, top_k: int) -> list[Any]:
        return await _retrieve_bm25(bm25_retriever, query, top_k)

    async def hybrid(query: str, top_k: int) -> list[Any]:
        return await _retrieve_hybrid(hybrid_retriever, query, top_k, enable_reranking=False, enable_query_expansion=False)

    async def hybrid_reranker(query: str, top_k: int) -> list[Any]:
        return await _retrieve_hybrid(hybrid_retriever, query, top_k, enable_reranking=True, enable_query_expansion=False)

    async def hybrid_expansion_reranker(query: str, top_k: int) -> list[Any]:
        return await _retrieve_hybrid(hybrid_retriever, query, top_k, enable_reranking=True, enable_query_expansion=True)

    methods = {
        "dense_only": dense_only,
        "bm25_only": bm25_only,
        "hybrid": hybrid,
        "hybrid+reranker": hybrid_reranker,
        "hybrid+expansion+reranker": hybrid_expansion_reranker,
    }

    if warmup_runs > 0:
        logger.info("Running warmup queries", count=warmup_runs)

    async def _warmup():
        queries = ["remote work policy", "VPN access", "expense report deadline", "incident response", "data privacy"]
        for _ in range(warmup_runs):
            for q in queries:
                for name, fn in methods.items():
                    try:
                        await fn(q, 10)
                    except Exception:
                        pass

    asyncio.run(_warmup())

    return methods


async def _retrieve_dense(hybrid_retriever: HybridRetriever, query: str, top_k: int) -> list[Any]:
    import time
    start = time.perf_counter()
    query_vector = hybrid_retriever.embedding_service.embed_query(query)
    dense_raw = hybrid_retriever.qdrant_service.search(query_vector=query_vector.tolist(), top_k=top_k)
    elapsed = (time.perf_counter() - start) * 1000
    logger.debug("dense_retrieval", query=query, count=len(dense_raw), ms=round(elapsed, 2))
    return [
        __import__("src.core.models", fromlist=["RetrievalResult"]).RetrievalResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            text=r["text"],
            score=r["score"],
            retrieval_method="dense",
            metadata=r.get("metadata", {}),
        )
        for r in dense_raw
    ]


async def _retrieve_bm25(bm25_retriever: BM25Retriever, query: str, top_k: int) -> list[Any]:
    import time
    start = time.perf_counter()
    raw = bm25_retriever.search(query, top_k=top_k)
    elapsed = (time.perf_counter() - start) * 1000
    logger.debug("bm25_retrieval", query=query, count=len(raw), ms=round(elapsed, 2))
    results = []
    for chunk_id, score in raw:
        text = ""
        if chunk_id in bm25_retriever._chunk_ids:
            idx = bm25_retriever._chunk_ids.index(chunk_id)
            text = bm25_retriever._documents[idx]
        results.append(
            __import__("src.core.models", fromlist=["RetrievalResult"]).RetrievalResult(
                chunk_id=chunk_id,
                document_id=chunk_id.split("_chunk_")[0] if "_chunk_" in chunk_id else chunk_id,
                text=text,
                score=score,
                retrieval_method="sparse",
                metadata={},
            )
        )
    return results


async def _retrieve_hybrid(
    hybrid_retriever: HybridRetriever,
    query: str,
    top_k: int,
    enable_reranking: bool,
    enable_query_expansion: bool,
) -> list[Any]:
    result = hybrid_retriever.search(
        query=query,
        dense_top_k=top_k,
        sparse_top_k=top_k,
        rerank_top_k=top_k,
        fusion_method=settings.hybrid_method,
        fusion_alpha=settings.hybrid_alpha,
        enable_query_expansion=enable_query_expansion,
        enable_reranking=enable_reranking,
    )
    return [
        __import__("src.core.models", fromlist=["RetrievalResult"]).RetrievalResult(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            text=r["text"],
            score=r["score"],
            retrieval_method=r["retrieval_method"],
            metadata=r.get("metadata", {}),
        )
        for r in result["results"]
    ]


def _verify_dependencies() -> list[str]:
    missing = []
    try:
        import qdrant_client  # noqa: F401
    except ImportError:
        missing.append("qdrant-client")
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        missing.append("sentence-transformers")
    try:
        import rank_bm25  # noqa: F401
    except ImportError:
        missing.append("rank-bm25")
    return missing


def _verify_qdrant() -> bool:
    try:
        import httpx
        response = httpx.get(f"{settings.qdrant_url}/healthz", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Run RAG benchmark with real retrieval")
    parser.add_argument(
        "--num-queries",
        type=int,
        default=35,
        help="Number of queries to evaluate",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Directory to save reports",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run ablation study",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild BM25 and Qdrant indexes",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of benchmark runs (for latency aggregation)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device for models (cpu/cuda). Auto-detected if not set.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of warmup runs before measurement",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output",
    )
    args = parser.parse_args()

    missing = _verify_dependencies()
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        return 1

    if not _verify_qdrant():
        print("Qdrant is not reachable. Start it with: docker compose up -d qdrant")
        return 1

    device = _resolve_device(args.device)
    logger.info("Benchmark configuration", device=device, num_queries=args.num_queries, runs=args.runs)

    dataset = generate_synthetic_dataset(args.num_queries)
    documents = generate_documents()
    chunks = build_chunks_from_documents(documents)

    methods = _build_retrieval_methods(chunks, device, args.rebuild_index, warmup_runs=args.warmup)

    all_results = []
    wall_start = time.perf_counter()

    for run_idx in range(args.runs):
        logger.info("Benchmark run", run=run_idx + 1, total=args.runs)
        runner = BenchmarkRunner(
            retrieval_methods=methods,
            ks=[1, 3, 5, 10],
            num_queries=args.num_queries,
        )
        results = asyncio.run(runner.run(dataset))
        all_results.append(results)

    wall_ms = (time.perf_counter() - wall_start) * 1000

    if args.runs > 1:
        merged = _merge_runs(all_results)
        results = merged
    else:
        results = all_results[0]

    generator = ReportGenerator(output_dir=args.output_dir)
    generator.save_reports(results)

    summary = results.get("summary", {})
    if not args.quiet:
        print("\n" + "=" * 60)
        print("BENCHMARK RESULTS")
        print("=" * 60)
        for method, metrics in summary.items():
            print(f"\n{method}:")
            for metric, value in metrics.items():
                print(f"  {metric}: {value:.4f}")

        latency = results.get("latency", {})
        if latency:
            print("\nLatency:")
            for method, stats in latency.items():
                mean = stats.get("mean")
                p50 = stats.get("p50")
                print(f"  {method}: mean={mean:.2f}ms, p50={p50:.2f}ms")

        failure = runner.get_failure_analysis()
        if failure.get("total_failures", 0) > 0:
            print(f"\nFailures: {failure['total_failures']} / {failure['total_queries_run']}")
        print("=" * 60 + "\n")

    logger.info("Benchmark complete", wall_ms=round(wall_ms, 2), output_dir=args.output_dir)
    return 0


def _merge_runs(results_list: list[dict[str, Any]]) -> dict[str, Any]:
    if not results_list:
        return {}
    base = results_list[0]
    experiments = base.get("experiments", {})

    for method in experiments:
        all_metrics = defaultdict(list)
        for run in results_list:
            exp = run.get("experiments", {}).get(method, {})
            for metric, value in exp.get("metrics", {}).items():
                if isinstance(value, (int, float)):
                    all_metrics[metric].append(value)
        if all_metrics:
            experiments[method]["metrics"] = {
                metric: sum(vals) / len(vals) for metric, vals in all_metrics.items()
            }

    base["experiments"] = experiments
    base["summary"] = {
        method: {metric: round(value, 4) for metric, value in data.get("metrics", {}).items()}
        for method, data in experiments.items()
    }
    return base


if __name__ == "__main__":
    sys.exit(main())
