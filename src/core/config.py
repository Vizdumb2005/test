from dataclasses import dataclass, field
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = True
    log_level: str = "info"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "enterprise_documents"
    qdrant_vector_size: int = 384

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embedding_batch_size: int = 32

    dense_top_k: int = 30
    sparse_top_k: int = 30
    rerank_top_k: int = 8

    hybrid_method: str = "rrf"
    hybrid_alpha: float = 0.65
    rrf_k: int = 60

    query_expansion_enabled: bool = True
    query_expansion_count: int = 3
    query_expansion_model: str = "gpt-4o-mini"

    chunk_size: int = 800
    chunk_overlap: int = 120
    chunking_strategy: str = "recursive"

    context_max_chunks: int = 8
    context_max_characters: int = 30000

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    max_upload_size_mb: int = 50


settings = Settings()
