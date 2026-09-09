from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.api.routes.health import router as health_router
from src.api.routes.documents import router as documents_router
from src.api.routes.search import router as search_router
from src.api.routes.query import router as query_router
from src.api.routes.debug import router as debug_router
from src.api.routes.evaluation import router as evaluation_router
from src.core.logging import logger
from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enterprise Hybrid RAG API", env=settings.app_env)
    yield
    logger.info("Shutting down Enterprise Hybrid RAG API")


app = FastAPI(
    title="Enterprise Hybrid RAG API",
    description="Production-grade Hybrid RAG system with evaluation pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(query_router)
app.include_router(debug_router)
app.include_router(evaluation_router)


@app.get("/")
async def root():
    return {"message": "Enterprise Hybrid RAG API", "version": "0.1.0"}
