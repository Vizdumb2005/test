from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from ...core.logging import logger
from ...core.config import settings
from ..schemas.schemas import IngestRequest, BatchIngestRequest, IngestResponse

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_pipeline():
    from src.ingestion.pipeline import IngestionPipeline
    return IngestionPipeline()


@router.post("/", response_model=IngestResponse)
async def ingest_document(request: IngestRequest):
    try:
        logger.info("Ingesting document", source=request.source)
        pipeline = _get_pipeline()
        chunks = pipeline.ingest(request.source, request.metadata)
        return IngestResponse(
            document_id=chunks[0].document_id if chunks else "",
            chunks_created=len(chunks),
            status="success",
            message=f"Ingested {len(chunks)} chunks"
        )
    except Exception as e:
        logger.error("Ingestion failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=list[IngestResponse])
async def batch_ingest(request: BatchIngestRequest):
    pipeline = _get_pipeline()
    results = []
    for source in request.sources:
        try:
            chunks = pipeline.ingest(source, request.common_metadata)
            results.append(IngestResponse(
                document_id=chunks[0].document_id if chunks else "",
                chunks_created=len(chunks),
                status="success",
                message=f"Ingested {len(chunks)} chunks"
            ))
        except Exception as e:
            logger.error("Batch ingestion failed", source=source, error=str(e))
            results.append(IngestResponse(
                document_id="",
                chunks_created=0,
                status="error",
                message=str(e)
            ))
    return results


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None)
):
    import json
    import os
    import tempfile
    from pathlib import Path

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_types = {".pdf", ".txt", ".md", ".docx"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")
        tmp.write(content)
        tmp_path = tmp.name

    try:
        pipeline = _get_pipeline()
        chunks = pipeline.ingest(tmp_path, meta)
        return IngestResponse(
            document_id=chunks[0].document_id if chunks else "",
            chunks_created=len(chunks),
            status="success",
            message=f"Ingested {len(chunks)} chunks"
        )
    finally:
        os.unlink(tmp_path)
