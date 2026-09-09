from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    document_id: str
    chunk_id: str
    source: str
    file_name: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    chunk_index: int
    document_type: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IngestRequest(BaseModel):
    source: str = Field(..., description="File path or URL to document")
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchIngestRequest(BaseModel):
    sources: list[str] = Field(..., min_length=1, max_length=50)
    common_metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    dense_top_k: Optional[int] = None
    sparse_top_k: Optional[int] = None
    rerank_top_k: Optional[int] = None
    hybrid_method: Optional[str] = None
    hybrid_alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    enable_query_expansion: Optional[bool] = None
    enable_reranking: Optional[bool] = None
    filters: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)
    include_context: bool = True
    enable_query_expansion: Optional[bool] = None
    enable_reranking: Optional[bool] = None


class RetrievalResultItem(BaseModel):
    rank: int
    score: float
    retrieval_method: str
    document_id: str
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: list[RetrievalResultItem]
    latency_ms: dict[str, float]
    expanded_queries: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[dict[str, Any]]
    confidence: float
    latency_ms: dict[str, float]
    retrieval_results: list[RetrievalResultItem]


class HealthResponse(BaseModel):
    status: str
    version: str
    qdrant_connected: bool
    bm25_loaded: bool
    models_loaded: bool


class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int
    status: str
    message: str


class DebugRetrievalResponse(BaseModel):
    query: str
    expanded_queries: list[str]
    dense_results: list[dict[str, Any]]
    sparse_results: list[dict[str, Any]]
    fusion_results: list[dict[str, Any]]
    reranked_results: list[dict[str, Any]]
    final_context: list[dict[str, Any]]
    latency_ms: dict[str, float]


class EvaluationResultResponse(BaseModel):
    run_id: str
    timestamp: str
    total_queries: int
    metrics: dict[str, Any]
    ablation_results: dict[str, Any]
    failure_analysis: list[dict[str, Any]]
    latency_stats: dict[str, Any]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: Optional[str] = None
