import argparse
import asyncio
import sys
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

    return {
        "dense_only": dense_only,
        "bm25_only": bm25_only,
        "hybrid": hybrid,
        "hybrid+reranker": hybrid_reranker,
        "hybrid+expansion+reranker": hybrid_expansion_reranker,
    }


async def _retrieve_dense(hybrid_retriever: HybridRetriever, query: str, top_k: int) -> list[Any]:
    query_vector = hybrid_retriever.embedding_service.embed_query(query)
    dense_raw = hybrid_retriever.qdrant_service.search(query_vector=query_vector.tolist(), top_k=top_k)
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
    raw = bm25_retriever.search(query, top_k=top_k)
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
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
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
        "--device",
        type=str,
        default=None,
        help="Device for models (cpu/cuda). Auto-detected if not set.",
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
    logger.info("Evaluation configuration", device=device, num_queries=args.num_queries)

    dataset = generate_synthetic_dataset(args.num_queries)
    documents = generate_documents()
    chunks = build_chunks_from_documents(documents)

    methods = _build_retrieval_methods(chunks, device, args.rebuild_index)
    runner = BenchmarkRunner(
        retrieval_methods=methods,
        ks=[1, 3, 5, 10],
        num_queries=args.num_queries,
    )
    generator = ReportGenerator(output_dir=args.output_dir)

    if args.ablation:
        logger.info("Starting ablation benchmark", num_queries=args.num_queries)
        runner.retrieval_methods = methods
        results = asyncio.run(runner.run(dataset))
    else:
        logger.info("Starting benchmark", num_queries=args.num_queries)
        results = asyncio.run(runner.run(dataset))

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

    logger.info("Evaluation complete", output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
