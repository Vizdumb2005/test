from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    source: str
    file_name: str
    text: str
    chunk_index: int
    page_number: Optional[int] = None
    section: Optional[str] = None
    document_type: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Document:
    document_id: str
    source: str
    file_name: str
    document_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    page_count: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    retrieval_method: str
    metadata: dict[str, Any] = field(default_factory=dict)
    rank: Optional[int] = None


@dataclass
class RerankedResult:
    chunk_id: str
    document_id: str
    text: str
    original_score: float
    rerank_score: float
    final_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    query: str
    results: list[RetrievalResult]
    latency_ms: dict[str, float]
    expanded_queries: list[str] = field(default_factory=list)
    debug_info: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedAnswer:
    query: str
    answer: str
    citations: list[dict[str, Any]]
    confidence: float
    latency_ms: dict[str, float]
    retrieval_results: list[RetrievalResult]


@dataclass
class EvaluationSample:
    query: str
    relevant_document_ids: list[str] = field(default_factory=list)
    relevant_chunk_ids: list[str] = field(default_factory=list)
    expected_answer: str = ""
    difficulty: str = "medium"
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    name: str
    value: float
    retrieval_method: str
    query_id: Optional[str] = None
    category: Optional[str] = None
