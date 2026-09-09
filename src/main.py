from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.api.routes.health import router as health_router
from src.api.routes.documents import router as documents_router
from src.api.routes.search import router as search_router
from src.api.routes.query import router as query_router
from src.api.routes.debug import router as debug_router
from src.api.routes.evaluation import router as evaluation_router
from src.api.routes.benchmark import router as benchmark_router
from src.api.routes.system import router as system_router
from src.core.logging import logger
from src.core.config import settings
from src.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Hybrid RAG API", env=settings.app_env)
    yield
    logger.info("Shutting down Enterprise Hybrid RAG API")


def _cors_origins() -> list[str]:
    if settings.app_env != "production":
        return ["*"]
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


app = FastAPI(
    title="Enterprise Hybrid RAG API",
    description=(
        "Evaluation-driven hybrid retrieval (dense + BM25 + CrossEncoder reranking) "
        "with retrieval-transparent answers. See /api/system/status and /api/config/public."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "System", "description": "Status, config, monitoring, reports, document index."},
        {"name": "health", "description": "Liveness / readiness probes."},
        {"name": "documents", "description": "Ingest, upload and manage documents."},
        {"name": "search", "description": "Hybrid retrieval search."},
        {"name": "query", "description": "Retrieval-augmented question answering."},
        {"name": "debug", "description": "Retrieval pipeline inspection traces."},
        {"name": "evaluation", "description": "Evaluation and benchmark runs."},
    ],
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    detail = str(exc) if settings.debug else "Internal server error."
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": detail, "request_id": _request_id(request)},
    )


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):  # pragma: no cover - defensive
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "detail": "Too many requests.", "request_id": _request_id(request)},
    )


# Canonical routes (preserved for existing consumers)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(debug_router)
app.include_router(evaluation_router)
app.include_router(benchmark_router)
app.include_router(system_router)  # paths already live under /api/...

# Versioned aliases: /api/v1/... (same handlers, non-breaking addition;
# system router is already version-neutral under /api/ so it is not duplicated)
app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(debug_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    return {"message": "Enterprise Hybrid RAG API", "version": APP_VERSION}
