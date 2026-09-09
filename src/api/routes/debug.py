from fastapi import APIRouter, HTTPException, Request
from ...api.schemas.schemas import SearchRequest, DebugRetrievalResponse
from ...core.logging import logger
from ...core.config import settings

router = APIRouter(tags=["debug"])


@router.post("/debug/retrieval", response_model=DebugRetrievalResponse)
async def debug_retrieval(request: SearchRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", None)
    try:
        logger.info("Debug retrieval request", query=request.query, request_id=request_id)

        from src.retrieval.hybrid.fusion import HybridRetriever
        hybrid_retriever = HybridRetriever()

        dense_top_k = request.dense_top_k or settings.dense_top_k
        sparse_top_k = request.sparse_top_k or settings.sparse_top_k
        rerank_top_k = request.rerank_top_k or settings.rerank_top_k
        hybrid_method = request.hybrid_method or settings.hybrid_method
        hybrid_alpha = request.hybrid_alpha if request.hybrid_alpha is not None else settings.hybrid_alpha

        debug_info = hybrid_retriever.debug_search(
            query=request.query,
            dense_top_k=dense_top_k,
            sparse_top_k=sparse_top_k,
            rerank_top_k=rerank_top_k,
            fusion_method=hybrid_method,
            fusion_alpha=hybrid_alpha,
            enable_query_expansion=request.enable_query_expansion,
            enable_reranking=request.enable_reranking,
        )

        return DebugRetrievalResponse(
            query=request.query,
            expanded_queries=debug_info.get("expanded_queries", []),
            dense_results=debug_info.get("dense_results", []),
            sparse_results=debug_info.get("sparse_results", []),
            fusion_results=debug_info.get("fusion_results", []),
            reranked_results=debug_info.get("reranked_results", []),
            final_context=debug_info.get("final_context", []),
            latency_ms=debug_info.get("latency_ms", {}),
            request_id=request_id,
        )
    except Exception as e:
        logger.error("Debug retrieval failed", error=str(e), request_id=request_id)
        raise HTTPException(status_code=500, detail=(str(e) if settings.debug else 'Request failed. Check server logs with the X-Request-ID header.'))
