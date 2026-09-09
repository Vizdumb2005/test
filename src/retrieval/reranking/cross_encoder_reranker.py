from typing import Any, Optional

import numpy as np
import structlog
from sentence_transformers import CrossEncoder

from src.core.config import settings
from src.core.models import RerankedResult, RetrievalResult

logger = structlog.get_logger("cross_encoder_reranker")


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: Optional[str] = None,
        max_length: int = 512,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or settings.reranker_model
        self.max_length = max_length
        self.device = device
        self._model: Optional[CrossEncoder] = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("loading_reranker_model", model=self.model_name)
            self._model = CrossEncoder(self.model_name, max_length=self.max_length, device=self.device)
            logger.info("reranker_model_loaded", model=self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RerankedResult]:
        top_k = top_k or settings.rerank_top_k

        if not candidates:
            return []

        if len(candidates) == 1:
            result = candidates[0]
            return [
                RerankedResult(
                    chunk_id=result.chunk_id,
                    document_id=result.document_id,
                    text=result.text,
                    original_score=result.score,
                    rerank_score=1.0,
                    final_score=1.0,
                    metadata=result.metadata,
                )
            ]

        logger.debug("reranking_candidates", query_length=len(query), candidate_count=len(candidates))

        pairs = [[query, candidate.text] for candidate in candidates]
        scores = self.model.predict(pairs)

        reranked = []
        for candidate, rerank_score in zip(candidates, scores):
            final_score = float(rerank_score)
            reranked.append(
                RerankedResult(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    text=candidate.text,
                    original_score=candidate.score,
                    rerank_score=float(rerank_score),
                    final_score=final_score,
                    metadata=candidate.metadata,
                )
            )

        reranked.sort(key=lambda x: x.final_score, reverse=True)
        reranked = reranked[:top_k]

        logger.debug(
            "reranking_complete",
            input_count=len(candidates),
            output_count=len(reranked),
            top_score=round(reranked[0].final_score, 4) if reranked else None,
        )
        return reranked
