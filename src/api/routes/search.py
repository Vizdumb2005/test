from fastapi import APIRouter, HTTPException, Request
from ...api.schemas.schemas import SearchRequest, SearchResponse
from ...core.logging import logger
from ...core.config import settings

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", None)
    try:
        logger.info("Search request", query=request.query, top_k=request.top_k, request_id=request_id)

        from src.retrieval.hybrid.fusion import HybridRetriever
        hybrid_retriever = HybridRetriever()

        dense_top_k = request.dense_top_k or settings.dense_top_k
        sparse_top_k = request.sparse_top_k or settings.sparse_top_k
        rerank_top_k = request.rerank_top_k or settings.rerank_top_k
        hybrid_method = request.hybrid_method or settings.hybrid_method
        hybrid_alpha = request.hybrid_alpha if request.hybrid_alpha is not None else settings.hybrid_alpha

        results = hybrid_retriever.search(
            query=request.query,
            dense_top_k=dense_top_k,
            sparse_top_k=sparse_top_k,
            rerank_top_k=rerank_top_k,
            fusion_method=hybrid_method,
            fusion_alpha=hybrid_alpha,
            enable_query_expansion=request.enable_query_expansion,
            enable_reranking=request.enable_reranking,
        )

        try:
            from ...core.telemetry import telemetry
            telemetry.record_retrieval_run(results.get("latency_ms", {}))
        except Exception:
            pass

        return SearchResponse(
            query=request.query,
            results=results["results"],
            latency_ms=results["latency_ms"],
            expanded_queries=results.get("expanded_queries", []),
            request_id=request_id,
        )
    except Exception as e:
        logger.error("Search failed", error=str(e), request_id=request_id)
        raise HTTPException(status_code=500, detail=(str(e) if settings.debug else 'Request failed. Check server logs with the X-Request-ID header.'))
