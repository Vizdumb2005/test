import logging
import time
from collections import OrderedDict
from typing import Any, Optional

import numpy as np
import structlog
from sentence_transformers import SentenceTransformer

from src.core.config import settings

logger = structlog.get_logger("embedding_service")


class EmbeddingService:
    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
        device: Optional[str] = None,
        cache_maxsize: int = 2048,
    ) -> None:
        self.model_name = model_name or settings.embedding_model
        self.batch_size = batch_size or settings.embedding_batch_size
        self.device = device or self._resolve_device()
        self.cache_maxsize = cache_maxsize
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None

    def _resolve_device(self) -> str:
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("loading_embedding_model", model=self.model_name, device=self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = int(self._model.get_sentence_embedding_dimension())
            logger.info("embedding_model_loaded", model=self.model_name, dimension=self._dimension)
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            _ = self.model
        assert self._dimension is not None
        return self._dimension

    def _get_from_cache(self, text: str) -> Optional[np.ndarray]:
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        return None

    def _put_in_cache(self, text: str, embedding: np.ndarray) -> None:
        if text in self._cache:
            self._cache.move_to_end(text)
        else:
            self._cache[text] = embedding
            if len(self._cache) > self.cache_maxsize:
                self._cache.popitem(last=False)

    def embed_texts(
        self,
        texts: list[str],
        show_progress: bool = False,
        use_cache: bool = True,
    ) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        logger.debug("embedding_batch", count=len(texts), batch_size=self.batch_size)

        embeddings: list[np.ndarray] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for idx, text in enumerate(texts):
            cached = self._get_from_cache(text) if use_cache else None
            if cached is not None:
                embeddings.append(cached)
            else:
                embeddings.append(None)
                uncached_texts.append(text)
                uncached_indices.append(idx)

        if uncached_texts:
            start = time.perf_counter()
            try:
                new_embeddings = self.model.encode(
                    uncached_texts,
                    batch_size=self.batch_size,
                    show_progress_bar=show_progress,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                new_embeddings = new_embeddings.astype(np.float32)
            except Exception as exc:
                logger.error("embedding_failed", error=str(exc), model=self.model_name)
                raise RuntimeError(f"Embedding generation failed: {exc}") from exc

            elapsed = time.perf_counter() - start
            logger.debug(
                "embedding_complete",
                count=len(uncached_texts),
                elapsed_ms=round(elapsed * 1000, 2),
            )

            for idx, embedding in zip(uncached_indices, new_embeddings):
                embeddings[idx] = embedding
                if use_cache:
                    self._put_in_cache(texts[idx], embedding)

        return np.stack(embeddings, axis=0)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_texts([query])[0]

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.debug("embedding_cache_cleared")
