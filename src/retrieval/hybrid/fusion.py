from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import structlog

from src.core.config import settings
from src.core.models import RetrievalResult

logger = structlog.get_logger("fusion")


@dataclass
class FusionResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    retrieval_method: str
    metadata: dict[str, Any]


class Fusion:
    @staticmethod
    def reciprocal_rank_fusion(
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
        k: Optional[int] = None,
        top_k: Optional[int] = None,
    ) -> list[FusionResult]:
        k = k or settings.rrf_k
        top_k = top_k or settings.dense_top_k

        rrf_scores: dict[str, dict[str, Any]] = {}

        for rank, result in enumerate(dense_results, start=1):
            rrf_score = 1.0 / (k + rank)
            if result.chunk_id not in rrf_scores:
                rrf_scores[result.chunk_id] = {
                    "document_id": result.document_id,
                    "text": result.text,
                    "score": 0.0,
                    "metadata": dict(result.metadata),
                }
            rrf_scores[result.chunk_id]["score"] += rrf_score

        for rank, result in enumerate(sparse_results, start=1):
            rrf_score = 1.0 / (k + rank)
            if result.chunk_id not in rrf_scores:
                rrf_scores[result.chunk_id] = {
                    "document_id": result.document_id,
                    "text": result.text,
                    "score": 0.0,
                    "metadata": dict(result.metadata),
                }
            rrf_scores[result.chunk_id]["score"] += rrf_score

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]

        results = []
        for chunk_id, item in sorted_items:
            results.append(
                FusionResult(
                    chunk_id=chunk_id,
                    document_id=item["document_id"],
                    text=item["text"],
                    score=item["score"],
                    retrieval_method="rrf",
                    metadata=item["metadata"],
                )
            )

        logger.debug("rrf_complete", dense_count=len(dense_results), sparse_count=len(sparse_results), fused=len(results))
        return results

    @staticmethod
    def weighted_score_fusion(
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
        alpha: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> list[FusionResult]:
        alpha = alpha if alpha is not None else settings.hybrid_alpha
        top_k = top_k or settings.dense_top_k

        dense_scores = Fusion._normalize_scores(dense_results)
        sparse_scores = Fusion._normalize_scores(sparse_results)

        combined: dict[str, dict[str, Any]] = {}

        for result in dense_results:
            score = alpha * dense_scores.get(result.chunk_id, 0.0)
            combined[result.chunk_id] = {
                "document_id": result.document_id,
                "text": result.text,
                "score": score,
                "metadata": dict(result.metadata),
            }

        for result in sparse_results:
            sparse_score = sparse_scores.get(result.chunk_id, 0.0)
            if result.chunk_id in combined:
                combined[result.chunk_id]["score"] += (1.0 - alpha) * sparse_score
            else:
                combined[result.chunk_id] = {
                    "document_id": result.document_id,
                    "text": result.text,
                    "score": (1.0 - alpha) * sparse_score,
                    "metadata": dict(result.metadata),
                }

        sorted_items = sorted(combined.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]

        results = []
        for chunk_id, item in sorted_items:
            results.append(
                FusionResult(
                    chunk_id=chunk_id,
                    document_id=item["document_id"],
                    text=item["text"],
                    score=item["score"],
                    retrieval_method="weighted_fusion",
                    metadata=item["metadata"],
                )
            )

        logger.debug(
            "weighted_fusion_complete",
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            alpha=alpha,
            fused=len(results),
        )
        return results

    @staticmethod
    def _normalize_scores(results: list[RetrievalResult]) -> dict[str, float]:
        if not results:
            return {}
        scores = np.array([r.score for r in results], dtype=np.float32)
        min_score = float(scores.min())
        max_score = float(scores.max())
        if max_score == min_score:
            return {r.chunk_id: 1.0 for r in results}
        normalized = (scores - min_score) / (max_score - min_score)
        return {r.chunk_id: float(normalized[i]) for i, r in enumerate(results)}


class HybridRetriever:
    def __init__(
        self,
        embedding_service: Optional[Any] = None,
        qdrant_service: Optional[Any] = None,
        bm25_retriever: Optional[Any] = None,
        query_expander: Optional[Any] = None,
        reranker: Optional[Any] = None,
    ) -> None:
        from src.retrieval.dense.embedding_service import EmbeddingService
        from src.retrieval.dense.qdrant_service import QdrantService
        from src.retrieval.sparse.bm25_retriever import BM25Retriever
        from src.retrieval.query_expansion.expander import QueryExpander
        from src.retrieval.reranking.cross_encoder_reranker import CrossEncoderReranker

        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.query_expander = query_expander or QueryExpander()
        self.reranker = reranker or CrossEncoderReranker()

    def search(
        self,
        query: str,
        dense_top_k: int = 30,
        sparse_top_k: int = 30,
        rerank_top_k: int = 8,
        fusion_method: str = "rrf",
        fusion_alpha: float = 0.65,
        enable_query_expansion: Optional[bool] = None,
        enable_reranking: Optional[bool] = None,
    ) -> dict[str, Any]:
        import time

        latency: dict[str, float] = {}
        start_total = time.perf_counter()

        use_query_expansion = enable_query_expansion if enable_query_expansion is not None else settings.query_expansion_enabled
        use_reranking = enable_reranking if enable_reranking is not None else True

        expanded_queries = []
        if use_query_expansion:
            t0 = time.perf_counter()
            expanded_queries = self.query_expander.expand(query)
            latency["query_expansion"] = (time.perf_counter() - t0) * 1000

        all_queries = [query] + expanded_queries

        t0 = time.perf_counter()
        query_vector = self.embedding_service.embed_query(query)
        latency["embedding"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        dense_raw = self.qdrant_service.search(query_vector=query_vector.tolist(), top_k=dense_top_k)
        latency["dense_search"] = (time.perf_counter() - t0) * 1000

        dense_results = [
            RetrievalResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                text=r["text"],
                score=r["score"],
                retrieval_method="dense",
                metadata=r.get("metadata", {}),
            )
            for r in dense_raw
        ]

        t0 = time.perf_counter()
        sparse_raw = self.bm25_retriever.search(query, top_k=sparse_top_k)
        latency["bm25"] = (time.perf_counter() - t0) * 1000

        sparse_results = []
        for chunk_id, score in sparse_raw:
            sparse_results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=chunk_id.split("_chunk_")[0] if "_chunk_" in chunk_id else chunk_id,
                    text=self.bm25_retriever._documents[self.bm25_retriever._chunk_ids.index(chunk_id)] if chunk_id in self.bm25_retriever._chunk_ids else "",
                    score=score,
                    retrieval_method="sparse",
                    metadata={},
                )
            )

        t0 = time.perf_counter()
        if fusion_method == "weighted":
            fused = Fusion.weighted_score_fusion(dense_results, sparse_results, alpha=fusion_alpha, top_k=rerank_top_k * 2)
        else:
            fused = Fusion.reciprocal_rank_fusion(dense_results, sparse_results, top_k=rerank_top_k * 2)
        latency["fusion"] = (time.perf_counter() - t0) * 1000

        fusion_results = [
            RetrievalResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.text,
                score=r.score,
                retrieval_method=r.retrieval_method,
                metadata=r.metadata,
            )
            for r in fused
        ]

        reranked_results = fusion_results
        if use_reranking and fusion_results:
            t0 = time.perf_counter()
            reranked = self.reranker.rerank(query, fusion_results, top_k=rerank_top_k)
            latency["reranking"] = (time.perf_counter() - t0) * 1000
            reranked_results = [
                RetrievalResult(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    text=r.text,
                    score=r.final_score,
                    retrieval_method="hybrid_reranked",
                    metadata=r.metadata,
                )
                for r in reranked
            ]

        latency["total"] = (time.perf_counter() - start_total) * 1000

        result_items = []
        for rank, r in enumerate(reranked_results, start=1):
            result_items.append({
                "rank": rank,
                "score": round(r.score, 4),
                "retrieval_method": r.retrieval_method,
                "document_id": r.document_id,
                "chunk_id": r.chunk_id,
                "text": r.text,
                "metadata": r.metadata,
            })

        logger.info("search_complete", query_length=len(query), results=len(result_items), total_ms=round(latency.get("total", 0), 2))
        return {
            "results": result_items,
            "latency_ms": latency,
            "expanded_queries": expanded_queries,
        }

    def debug_search(
        self,
        query: str,
        dense_top_k: int = 30,
        sparse_top_k: int = 30,
        rerank_top_k: int = 8,
        fusion_method: str = "rrf",
        fusion_alpha: float = 0.65,
        enable_query_expansion: Optional[bool] = None,
        enable_reranking: Optional[bool] = None,
    ) -> dict[str, Any]:
        import time

        use_query_expansion = enable_query_expansion if enable_query_expansion is not None else settings.query_expansion_enabled
        use_reranking = enable_reranking if enable_reranking is not None else True

        expanded_queries = []
        if use_query_expansion:
            expanded_queries = self.query_expander.expand(query)

        query_vector = self.embedding_service.embed_query(query)
        dense_raw = self.qdrant_service.search(query_vector=query_vector.tolist(), top_k=dense_top_k)
        dense_results = [
            {
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "text": r["text"][:200],
                "score": round(r["score"], 4),
                "metadata": r.get("metadata", {}),
            }
            for r in dense_raw
        ]

        sparse_raw = self.bm25_retriever.search(query, top_k=sparse_top_k)
        sparse_results = [
            {
                "chunk_id": chunk_id,
                "score": round(score, 4),
            }
            for chunk_id, score in sparse_raw
        ]

        dense_objs = [
            RetrievalResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                text=r["text"],
                score=r["score"],
                retrieval_method="dense",
                metadata=r.get("metadata", {}),
            )
            for r in dense_raw
        ]
        sparse_objs = []
        for chunk_id, score in sparse_raw:
            text = ""
            if chunk_id in self.bm25_retriever._chunk_ids:
                idx = self.bm25_retriever._chunk_ids.index(chunk_id)
                text = self.bm25_retriever._documents[idx]
            sparse_objs.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    document_id=chunk_id.split("_chunk_")[0] if "_chunk_" in chunk_id else chunk_id,
                    text=text,
                    score=score,
                    retrieval_method="sparse",
                    metadata={},
                )
            )

        if fusion_method == "weighted":
            fused = Fusion.weighted_score_fusion(dense_objs, sparse_objs, alpha=fusion_alpha, top_k=rerank_top_k * 2)
        else:
            fused = Fusion.reciprocal_rank_fusion(dense_objs, sparse_objs, top_k=rerank_top_k * 2)

        fusion_results = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "text": r.text[:200],
                "score": round(r.score, 4),
                "retrieval_method": r.retrieval_method,
            }
            for r in fused
        ]

        reranked_results = fusion_results
        if use_reranking and fused:
            reranked = self.reranker.rerank(query, dense_objs[:len(fused)] + sparse_objs[:len(fused)], top_k=rerank_top_k)
            reranked_results = [
                {
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "text": r.text[:200],
                    "original_score": round(r.original_score, 4),
                    "rerank_score": round(r.rerank_score, 4),
                    "final_score": round(r.final_score, 4),
                }
                for r in reranked
            ]

        final_context = [r for r in fusion_results[:rerank_top_k]]

        return {
            "expanded_queries": expanded_queries,
            "dense_results": dense_results,
            "sparse_results": sparse_results,
            "fusion_results": fusion_results,
            "reranked_results": reranked_results,
            "final_context": final_context,
        }
