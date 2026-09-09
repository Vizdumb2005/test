"""System routes: status, public config, monitoring, reports, document index.

Additive router — existing routes are untouched. All handlers degrade
gracefully (Qdrant down, no reports yet, empty index) with structured
responses instead of 500s.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.logging import logger

router = APIRouter(tags=["System"])

REPORTS_DIR = Path("reports")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _read_json(name: str) -> Optional[dict[str, Any]]:
    path = REPORTS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:  # corrupt file -> report honestly
        logger.warning("report_read_failed", file=name, error=str(exc))
        return {"_error": f"Could not parse {name}: {exc}"}


def _read_csv(name: str) -> Optional[list[dict[str, Any]]]:
    path = REPORTS_DIR / name
    if not path.exists():
        return None
    try:
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    except Exception as exc:
        logger.warning("report_read_failed", file=name, error=str(exc))
        return []


def _qdrant_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=settings.qdrant_url, timeout=5)


def _service_status(name: str, check) -> dict[str, Any]:
    try:
        detail = check() or {}
        return {"name": name, "status": "operational", **detail}
    except Exception as exc:
        return {"name": name, "status": "unavailable", "error": str(exc)[:300]}


# --------------------------------------------------------------------------- #
# Service status
# --------------------------------------------------------------------------- #

@router.get("/api/system/status")
async def system_status() -> dict[str, Any]:
    """Detailed per-service health. Never raises; degrades to unavailable."""

    def check_api() -> dict[str, Any]:
        return {"detail": "FastAPI process is serving this response", "version": "1.0.0"}

    def check_qdrant() -> dict[str, Any]:
        client = _qdrant_client()
        client.get_collections()
        info: dict[str, Any] = {"url": settings.qdrant_url}
        try:
            col = client.get_collection(settings.qdrant_collection)
            info["collection"] = settings.qdrant_collection
            info["points"] = int(col.points_count or 0)
        except Exception as exc:
            info["collection_note"] = f"Collection not ready: {exc!s}"[:200]
        return info

    def check_bm25() -> dict[str, Any]:
        from src.retrieval.sparse.bm25_retriever import BM25Retriever

        retriever = BM25Retriever()
        index_path = Path(retriever.index_path)
        if index_path.exists():
            try:
                retriever.load()
                return {"indexed_chunks": retriever.document_count, "index_path": str(index_path)}
            except Exception as exc:
                return {"status_override": "degraded", "error": str(exc)[:200]}
        return {"status_override": "degraded", "detail": "No BM25 index file yet — ingest documents to build it."}

    def check_embedding() -> dict[str, Any]:
        # Avoid loading the model per status poll; report configured model +
        # whether its weights are cached locally.
        from huggingface_hub import scan_cache_dir  # noqa: F401  (optional)

        return {"model": settings.embedding_model, "detail": "Lazy-loaded on first retrieval request."}

    def check_reranker() -> dict[str, Any]:
        return {"model": settings.reranker_model, "detail": "Lazy-loaded on first rerank request."}

    def check_llm() -> dict[str, Any]:
        provider = settings.llm_provider
        if provider == "mock":
            return {"provider": "mock", "model": settings.llm_model, "detail": "Demo mode: deterministic mock answers with real retrieval."}
        configured = bool(settings.llm_api_key)
        out: dict[str, Any] = {"provider": provider, "model": settings.llm_model}
        if configured:
            out["detail"] = "API key configured (never exposed via API)."
        else:
            out["status_override"] = "degraded"
            out["detail"] = "No LLM API key configured — set LLM_PROVIDER=mock for keyless demo mode."
        return out

    services = [
        _service_status("api", check_api),
        _service_status("qdrant", check_qdrant),
        _service_status("bm25", check_bm25),
        _service_status("embedding_model", check_embedding),
        _service_status("reranker", check_reranker),
        _service_status("llm", check_llm),
    ]
    for svc in services:
        override = svc.pop("status_override", None)
        if override:
            svc["status"] = override
    # Embedding/reranker availability: check local HF cache for the model dir.
    try:
        cache_hit = _model_cached(settings.embedding_model)
        for svc in services:
            if svc["name"] == "embedding_model":
                svc["weights_cached"] = cache_hit
            if svc["name"] == "reranker":
                svc["weights_cached"] = _model_cached(settings.reranker_model)
    except Exception:
        pass

    overall = "operational" if all(s["status"] == "operational" for s in services) else "degraded"
    if any(s["status"] == "unavailable" and s["name"] in {"api", "qdrant"} for s in services):
        overall = "degraded"
    return {"overall": overall, "services": services}


def _model_cached(model_id: str) -> bool:
    try:
        from huggingface_hub import scan_cache_dir

        cache = scan_cache_dir()
        needle = model_id.replace("/", "--").lower()
        for repo in cache.repos:
            if needle in repo.repo_id.lower() or model_id.lower() in repo.repo_id.lower():
                return True
        return False
    except Exception:
        # Fall back: snapshot dir naming under ~/.cache/huggingface/hub
        try:
            hub = Path.home() / ".cache" / "huggingface" / "hub"
            needle = ("models--" + model_id.replace("/", "--")).lower()
            return any(needle in p.name.lower() for p in hub.iterdir()) if hub.exists() else False
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# Public (non-secret) runtime configuration
# --------------------------------------------------------------------------- #

@router.get("/api/config/public")
async def public_config() -> dict[str, Any]:
    """Runtime-search configuration safe for browsers. Never includes secrets."""
    return {
        "runtime": {
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "dense_top_k": settings.dense_top_k,
            "sparse_top_k": settings.sparse_top_k,
            "rerank_top_k": settings.rerank_top_k,
            "hybrid_method": settings.hybrid_method,
            "hybrid_alpha": settings.hybrid_alpha,
            "query_expansion_enabled": settings.query_expansion_enabled,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "demo_mode": settings.llm_provider == "mock",
        },
        "environment": {
            "app_env": settings.app_env,
            "qdrant_collection": settings.qdrant_collection,
            "max_upload_size_mb": settings.max_upload_size_mb,
        },
        "note": "Secrets (API keys) are never exposed. Environment changes require server restart / redeploy.",
    }


# --------------------------------------------------------------------------- #
# Monitoring (current session telemetry)
# --------------------------------------------------------------------------- #

@router.get("/api/monitoring/summary")
async def monitoring_summary() -> dict[str, Any]:
    from src.core.telemetry import telemetry

    return telemetry.summary()


# --------------------------------------------------------------------------- #
# Reports (benchmark / evaluation artefacts)
# --------------------------------------------------------------------------- #

class ReportPayload(BaseModel):
    name: str
    available: bool
    data: Optional[Any] = None


@router.get("/api/reports/benchmark")
async def report_benchmark() -> dict[str, Any]:
    data = _read_json("benchmark.json")
    if data is None:
        raise HTTPException(status_code=404, detail="No benchmark report yet. Run `make benchmark` or POST /benchmark/run.")
    return {"available": True, "data": data}


@router.get("/api/reports/ablation")
async def report_ablation() -> dict[str, Any]:
    rows = _read_csv("ablation.csv")
    if rows is None:
        raise HTTPException(status_code=404, detail="No ablation report yet.")
    return {"available": True, "rows": rows}


@router.get("/api/reports/latency")
async def report_latency() -> dict[str, Any]:
    raw = _read_json("latency.json")
    rows = _read_csv("latency.csv")
    if raw is None and rows is None:
        raise HTTPException(status_code=404, detail="No latency report yet.")
    return {"available": True, "raw": raw, "by_stage": rows}


@router.get("/api/reports/category")
async def report_category() -> dict[str, Any]:
    rows = _read_csv("retrieval_by_category.csv")
    if rows is None:
        raise HTTPException(status_code=404, detail="No category report yet.")
    return {"available": True, "rows": rows}


@router.get("/api/reports/failures")
async def report_failures(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    data = _read_json("failure_analysis.json")
    if data is None:
        raise HTTPException(status_code=404, detail="No failure analysis yet.")
    failures = data.get("failures", data if isinstance(data, list) else [])
    if isinstance(failures, dict):
        failures = failures.get("failures", [])
    total = len(failures)
    start = (page - 1) * page_size
    return {
        "available": True,
        "generated_at": data.get("generated_at") if isinstance(data, dict) else None,
        "summary": data.get("summary") if isinstance(data, dict) else None,
        "total": total,
        "page": page,
        "page_size": page_size,
        "failures": failures[start: start + page_size],
    }


@router.get("/api/reports/export")
async def export_report(kind: str = Query(default="benchmark")) -> PlainTextResponse:
    """Download generated CSV reports (benchmark, ablation, latency, category)."""
    mapping = {
        "benchmark": "benchmark.csv",
        "ablation": "ablation.csv",
        "latency": "latency.csv",
        "category": "retrieval_by_category.csv",
    }
    fname = mapping.get(kind)
    if not fname:
        raise HTTPException(status_code=400, detail=f"Unknown export kind: {kind}")
    path = REPORTS_DIR / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No {kind} report available yet.")
    return PlainTextResponse(path.read_text(), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


# --------------------------------------------------------------------------- #
# Document index (aggregated from Qdrant, BM25 fallback)
# --------------------------------------------------------------------------- #

def _aggregate_documents() -> list[dict[str, Any]]:
    """Aggregate chunk-level payloads into per-document summaries."""
    docs: dict[str, dict[str, Any]] = {}

    def _add(document_id: str, file_name: str, source: str, chunk_id: str,
             text: str, chunk_index: int, page: Any, section: Any, doc_type: str) -> None:
        entry = docs.get(document_id)
        if entry is None:
            entry = {
                "document_id": document_id, "file_name": file_name or document_id,
                "source": source or file_name or document_id, "document_type": doc_type or "unknown",
                "chunk_count": 0, "chunk_ids": [], "sample_text": text[:300] if text else "",
                "pages": set(), "sections": set(),
            }
            docs[document_id] = entry
        entry["chunk_count"] += 1
        entry["chunk_ids"].append(chunk_id)
        if page is not None:
            entry["pages"].add(page)
        if section:
            entry["sections"].add(section)

    # Primary: Qdrant payloads (authoritative, has metadata).
    try:
        client = _qdrant_client()
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=settings.qdrant_collection, limit=500,
                offset=offset, with_payload=True, with_vectors=False,
            )
            for pt in points:
                p = pt.payload or {}
                _add(str(p.get("document_id", pt.id)), str(p.get("file_name", "")),
                     str(p.get("source", "")), str(p.get("chunk_id", pt.id)),
                     str(p.get("text", "")), int(p.get("chunk_index", 0) or 0),
                     p.get("page_number"), p.get("section"),
                     str(p.get("document_type", "unknown")))
            if offset is None:
                break
    except Exception as exc:
        logger.warning("doc_index_qdrant_failed", error=str(exc))

    # Fallback: BM25 pickle (chunk ids only) when Qdrant is empty/unreachable.
    if not docs:
        try:
            from src.retrieval.sparse.bm25_retriever import BM25Retriever

            r = BM25Retriever()
            if Path(r.index_path).exists():
                r.load()
                import pickle as _pickle

                state = _pickle.loads(Path(r.index_path).read_bytes())
                for cid, text in zip(state.get("chunk_ids", []), state.get("documents", [])):
                    doc_id = str(cid).rsplit("_chunk_", 1)[0] if "_chunk_" in str(cid) else str(cid)
                    _add(doc_id, doc_id, doc_id, str(cid), str(text), 0, None, None, "unknown")
        except Exception as exc:
            logger.warning("doc_index_bm25_failed", error=str(exc))

    out = []
    for d in docs.values():
        out.append({
            "document_id": d["document_id"], "file_name": d["file_name"], "source": d["source"],
            "document_type": d["document_type"], "chunk_count": d["chunk_count"],
            "page_count": len(d["pages"]), "sections": sorted(s for s in d["sections"] if s)[:10],
            "sample_text": d["sample_text"], "status": "indexed",
        })
    return sorted(out, key=lambda d: d["file_name"].lower())


@router.get("/api/documents/index")
async def documents_index(
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    docs = _aggregate_documents()
    if q:
        needle = q.lower()
        docs = [d for d in docs if needle in d["file_name"].lower() or needle in d["document_id"].lower()]
    total = len(docs)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "documents": docs[start: start + page_size]}


@router.get("/api/documents/index/{document_id}")
async def document_detail(
    document_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    try:
        from qdrant_client import models as qmodels

        client = _qdrant_client()
        points, _ = client.scroll(
            collection_name=settings.qdrant_collection, limit=2000,
            scroll_filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="document_id",
                                             match=qmodels.MatchValue(value=document_id))]),
            with_payload=True, with_vectors=False,
        )
        for pt in points:
            p = pt.payload or {}
            chunks.append({
                "chunk_id": str(p.get("chunk_id", pt.id)),
                "chunk_index": int(p.get("chunk_index", 0) or 0),
                "page_number": p.get("page_number"), "section": p.get("section"),
                "text": str(p.get("text", "")),
            })
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {exc}") from exc
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found in index.")
    chunks.sort(key=lambda c: c["chunk_index"])
    total = len(chunks)
    start = (page - 1) * page_size
    first = chunks[0]
    return {
        "document_id": document_id, "chunk_count": total, "status": "indexed",
        "page": page, "page_size": page_size, "total": total,
        "chunks": [{**c, "text": c["text"][:2000]} for c in chunks[start: start + page_size]],
    }


@router.delete("/api/documents/index/{document_id}")
async def document_delete(document_id: str) -> dict[str, Any]:
    """Remove a document's chunks from Qdrant and rebuild the BM25 index without them."""
    removed_qdrant = 0
    try:
        from qdrant_client import models as qmodels

        client = _qdrant_client()
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=qmodels.FilterSelector(filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="document_id",
                                             match=qmodels.MatchValue(value=document_id))])),
        )
        removed_qdrant = 1
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Qdrant delete failed: {exc}") from exc

    removed_bm25 = 0
    try:
        from src.retrieval.sparse.bm25_retriever import BM25Retriever
        import pickle as _pickle

        r = BM25Retriever()
        if Path(r.index_path).exists():
            state = _pickle.loads(Path(r.index_path).read_bytes())
            keep = [(c, t) for c, t in zip(state.get("chunk_ids", []), state.get("documents", []))
                    if not (str(c) == document_id or str(c).startswith(document_id + "_chunk_")
                            or str(c).rsplit("_chunk_", 1)[0] == document_id)]
            removed_bm25 = len(state.get("chunk_ids", [])) - len(keep)
            if keep:
                r.index_documents([t for _, t in keep], [c for c, _ in keep])
                r.save()
            else:
                Path(r.index_path).unlink()
    except Exception as exc:
        logger.warning("bm25_rebuild_after_delete_failed", error=str(exc))

    return {"document_id": document_id, "status": "deleted",
            "qdrant_delete_issued": bool(removed_qdrant), "bm25_chunks_removed": removed_bm25}
