from fastapi import APIRouter, HTTPException, Depends, Request
from ...api.schemas.schemas import QueryRequest, QueryResponse, RetrievalResultItem
from ...core.logging import logger
from ...core.config import settings
from ...core.models import QueryResult, GeneratedAnswer
from ...generation.prompts.templates import USER_PROMPT_TEMPLATE

router = APIRouter(tags=["query"])


def _get_hybrid_retriever():
    from src.retrieval.hybrid.fusion import HybridRetriever
    return HybridRetriever()


def _build_prompt(query: str, context_chunks: list) -> str:
    if not context_chunks:
        return f"You are an enterprise assistant. Question: {query}"
    parts = []
    for i, chunk in enumerate(context_chunks):
        source = getattr(chunk, "source", "") or getattr(chunk, "file_name", "") or "unknown"
        parts.append(f"[{i + 1}] Source: {source}\n{chunk.text}")
    ctx = "\n\n".join(parts)
    return USER_PROMPT_TEMPLATE.format(context=ctx, query=query)


def _extract_citations(context_chunks: list, answer_text: str) -> list[dict]:
    citations = []
    for i, chunk in enumerate(context_chunks[:3]):
        marker = f"[{i + 1}]"
        citations.append({
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source": chunk.source or chunk.file_name,
            "file_name": chunk.file_name,
            "marker": marker,
            "text": chunk.text[:200],
        })
    return citations


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request):
    request_id = getattr(http_request.state, "request_id", None)
    try:
        logger.info("Query request", query=request.query, request_id=request_id)

        hybrid_retriever = _get_hybrid_retriever()

        dense_top_k = settings.dense_top_k
        sparse_top_k = settings.sparse_top_k
        rerank_top_k = settings.rerank_top_k
        hybrid_method = settings.hybrid_method
        hybrid_alpha = settings.hybrid_alpha

        retrieval_results = hybrid_retriever.search(
            query=request.query,
            dense_top_k=dense_top_k,
            sparse_top_k=sparse_top_k,
            rerank_top_k=rerank_top_k,
            fusion_method=hybrid_method,
            fusion_alpha=hybrid_alpha,
            enable_query_expansion=request.enable_query_expansion,
            enable_reranking=request.enable_reranking,
        )

        context_chunks = []
        for r in retrieval_results["results"]:
            from src.core.models import Chunk
            context_chunks.append(
                Chunk(
                    chunk_id=r["chunk_id"],
                    document_id=r["document_id"],
                    source=r["metadata"].get("source", ""),
                    file_name=r["metadata"].get("file_name", ""),
                    text=r["text"],
                    chunk_index=r["metadata"].get("chunk_index", 0),
                    page_number=r["metadata"].get("page_number"),
                    section=r["metadata"].get("section"),
                    document_type=r["metadata"].get("document_type", "unknown"),
                    metadata=r["metadata"],
                )
            )

        prompt = _build_prompt(request.query, context_chunks)
        answer_text = f"Based on the retrieved context, here is the answer to: {request.query}"
        if context_chunks:
            answer_text += f"\n\n{context_chunks[0].text[:500]}"
        else:
            answer_text = "I do not know based on the provided context."

        citations = _extract_citations(context_chunks, answer_text)
        confidence = 0.8 if context_chunks else 0.2

        try:
            from ...core.telemetry import telemetry
            telemetry.record_retrieval_run(retrieval_results.get("latency_ms", {}))
        except Exception:
            pass

        return QueryResponse(
            query=request.query,
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            latency_ms=retrieval_results.get("latency_ms", {}),
            request_id=request_id,
            retrieval_results=[
                RetrievalResultItem(
                    rank=r["rank"],
                    score=r["score"],
                    retrieval_method=r["retrieval_method"],
                    document_id=r["document_id"],
                    chunk_id=r["chunk_id"],
                    text=r["text"],
                    metadata=r["metadata"],
                ) for r in retrieval_results["results"]
            ],
        )
    except Exception as e:
        logger.error("Query failed", error=str(e))
        raise HTTPException(status_code=500, detail=(str(e) if settings.debug else 'Request failed. Check server logs with the X-Request-ID header.'))
