from fastapi import APIRouter
from ...core.logging import logger
from ...core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    qdrant_connected = False
    bm25_loaded = False
    models_loaded = False

    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url)
        collections = client.get_collections()
        qdrant_connected = True
    except Exception as e:
        logger.warning("Qdrant health check failed", error=str(e))

    try:
        from ...retrieval.sparse.bm25_retriever import BM25Retriever
        retriever = BM25Retriever()
        bm25_loaded = retriever.is_loaded()
    except Exception as e:
        logger.warning("BM25 health check failed", error=str(e))

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(settings.embedding_model)
        models_loaded = True
    except Exception as e:
        logger.warning("Model health check failed", error=str(e))

    return {
        "status": "healthy" if all([qdrant_connected, bm25_loaded, models_loaded]) else "degraded",
        "version": "0.1.0",
        "qdrant_connected": qdrant_connected,
        "bm25_loaded": bm25_loaded,
        "models_loaded": models_loaded,
    }
