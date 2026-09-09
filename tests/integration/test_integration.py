import asyncio
import time
from typing import Any

import pytest

from src.core.models import RetrievalResult
from src.evaluation.datasets.synthetic import build_chunks_from_documents, generate_documents
from src.retrieval.dense.embedding_service import EmbeddingService
from src.retrieval.dense.qdrant_service import QdrantService
from src.retrieval.hybrid.fusion import HybridRetriever
from src.retrieval.sparse.bm25_retriever import BM25Retriever
from src.retrieval.reranking.cross_encoder_reranker import CrossEncoderReranker


def _qdrant_available() -> bool:
    try:
        import httpx
        response = httpx.get("http://localhost:6333/healthz", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def _skip_if_no_qdrant():
    if not _qdrant_available():
        pytest.skip("Qdrant is not available")


class TestQdrantIntegration:
    def test_qdrant_connectivity(self):
        _skip_if_no_qdrant()
        service = QdrantService()
        count = service.count()
        assert isinstance(count, int)

    def test_qdrant_upsert_and_search(self):
        _skip_if_no_qdrant()
        service = QdrantService(recreate=True)
        embedding_service = EmbeddingService()
        vector = embedding_service.embed_query("test query").tolist()
        points = [
            {
                "chunk_id": "test_c1",
                "document_id": "test_doc",
                "text": "This is a test document about testing.",
                "vector": vector,
                "metadata": {"source": "test"},
            }
        ]
        service.upsert(points)
        results = service.search(query_vector=vector, top_k=1)
        assert len(results) >= 1
        assert results[0]["chunk_id"] == "test_c1"


class TestEmbeddingIntegration:
    def test_embedding_model_loads(self):
        service = EmbeddingService()
        vector = service.embed_query("hello world")
        assert vector.shape[0] > 0
        assert service.dimension > 0

    def test_embedding_caching(self):
        service = EmbeddingService()
        v1 = service.embed_query("cached query")
        v2 = service.embed_query("cached query")
        assert (v1 == v2).all()


class TestBM25Integration:
    def test_bm25_index_and_search(self):
        retriever = BM25Retriever()
        documents = [
            "The quick brown fox jumps over the lazy dog",
            "A fast brown fox leaps across the sleepy hound",
            "Python is a programming language",
        ]
        chunk_ids = ["c1", "c2", "c3"]
        retriever.index_documents(documents, chunk_ids)
        results = retriever.search("quick fox", top_k=2)
        assert len(results) == 2
        assert results[0][0] == "c1"

    def test_bm25_persistence(self, tmp_path):
        retriever = BM25Retriever()
        documents = [
            "hello world python programming",
            "goodbye world java development",
            "hello python developer tools",
        ]
        chunk_ids = ["c1", "c2", "c3"]
        retriever.index_documents(documents, chunk_ids)
        index_path = str(tmp_path / "bm25.pkl")
        retriever.save(index_path)

        new_retriever = BM25Retriever()
        new_retriever.load(index_path)
        results = new_retriever.search("hello python", top_k=2)
        assert len(results) >= 1
        assert "c1" in [r[0] for r in results] or "c3" in [r[0] for r in results]


class TestHybridRetrievalIntegration:
    def test_hybrid_end_to_end(self):
        _skip_if_no_qdrant()
        documents = generate_documents()
        chunks = build_chunks_from_documents(documents)

        embedding_service = EmbeddingService()
        qdrant_service = QdrantService(recreate=True)
        bm25_retriever = BM25Retriever()

        document_texts = [chunk.text for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        bm25_retriever.index_documents(document_texts, chunk_ids)

        vectors = embedding_service.embed_texts(document_texts).tolist()
        points = []
        for chunk, vector in zip(chunks, vectors):
            points.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "vector": vector,
                    "metadata": chunk.metadata,
                }
            )
        qdrant_service.upsert(points)

        retriever = HybridRetriever(
            embedding_service=embedding_service,
            qdrant_service=qdrant_service,
            bm25_retriever=bm25_retriever,
        )
        result = retriever.search("remote work policy", dense_top_k=5, sparse_top_k=5, rerank_top_k=5, enable_reranking=False, enable_query_expansion=False)
        assert len(result["results"]) > 0
        assert result["results"][0]["chunk_id"] is not None


class TestCrossEncoderIntegration:
    def test_cross_encoder_loads_and_predicts(self):
        reranker = CrossEncoderReranker()
        candidates = [
            RetrievalResult(
                chunk_id="c1",
                document_id="d1",
                text="The remote work policy requires 3 days in office.",
                score=0.9,
                retrieval_method="dense",
            ),
            RetrievalResult(
                chunk_id="c2",
                document_id="d1",
                text="Employees get 15 days of PTO in their first year.",
                score=0.8,
                retrieval_method="dense",
            ),
        ]
        results = reranker.rerank("remote work policy", candidates, top_k=2)
        assert len(results) == 2
        assert hasattr(results[0], "final_score")
