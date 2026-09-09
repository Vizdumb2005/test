import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import structlog
from rank_bm25 import BM25Okapi

from src.core.config import settings

logger = structlog.get_logger("bm25_retriever")


class BM25Retriever:
    def __init__(
        self,
        k1: Optional[float] = None,
        b: Optional[float] = None,
        index_path: Optional[str] = None,
    ) -> None:
        self.k1 = k1 if k1 is not None else 1.5
        self.b = b if b is not None else 0.75
        self.index_path = Path(index_path) if index_path else Path("data/bm25_index.pkl")
        self._bm25: Optional[BM25Okapi] = None
        self._documents: list[str] = []
        self._chunk_ids: list[str] = []

    def index_documents(self, documents: list[str], chunk_ids: list[str]) -> None:
        if len(documents) != len(chunk_ids):
            raise ValueError("documents and chunk_ids must have the same length")

        tokenized = [doc.lower().split() for doc in documents]
        self._bm25 = BM25Okapi(tokenized, k1=self.k1, b=self.b)
        self._documents = documents
        self._chunk_ids = chunk_ids

        logger.info(
            "bm25_indexed",
            doc_count=len(documents),
            k1=self.k1,
            b=self.b,
        )

    def search(self, query: str, top_k: Optional[int] = None) -> list[tuple[str, float]]:
        top_k = top_k or settings.sparse_top_k

        if self._bm25 is None or not self._documents:
            logger.warning("bm25_index_empty")
            return []

        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self._chunk_ids[idx], float(scores[idx])))

        logger.debug("bm25_search", query_length=len(query), results=len(results))
        return results

    def save(self, path: Optional[str] = None) -> None:
        path = Path(path) if path else self.index_path
        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "k1": self.k1,
            "b": self.b,
            "documents": self._documents,
            "chunk_ids": self._chunk_ids,
            "tokenized": [doc.lower().split() for doc in self._documents],
        }

        with open(path, "wb") as f:
            pickle.dump(state, f)

        logger.info("bm25_index_saved", path=str(path), doc_count=len(self._documents))

    def load(self, path: Optional[str] = None) -> None:
        path = Path(path) if path else self.index_path

        if not path.exists():
            raise FileNotFoundError(f"BM25 index not found at {path}")

        with open(path, "rb") as f:
            state = pickle.load(f)

        self.k1 = state["k1"]
        self.b = state["b"]
        self._documents = state["documents"]
        self._chunk_ids = state["chunk_ids"]
        self._bm25 = BM25Okapi(state["tokenized"], k1=self.k1, b=self.b)

        logger.info(
            "bm25_index_loaded",
            path=str(path),
            doc_count=len(self._documents),
            k1=self.k1,
            b=self.b,
        )

    @property
    def document_count(self) -> int:
        return len(self._documents)

    def is_loaded(self) -> bool:
        return self._bm25 is not None
