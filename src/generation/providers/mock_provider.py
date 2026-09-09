import logging
from typing import Any

from src.core.models import Chunk, GeneratedAnswer
from src.generation.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class MockProvider:
    def __init__(self, response: str = "This is a mock answer based on the provided context.") -> None:
        self.response = response

    async def generate(
        self,
        prompt: str,
        context: list[Chunk],
        **kwargs: Any,
    ) -> GeneratedAnswer:
        if not context:
            answer = "I do not know based on the provided context."
        else:
            answer = self.response

        citations = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "source": chunk.source,
                "file_name": chunk.file_name,
                "marker": "[1]",
                "text": chunk.text[:200],
            }
            for chunk in context[:3]
        ]

        return GeneratedAnswer(
            query=prompt,
            answer=answer,
            citations=citations,
            confidence=0.75,
            latency_ms={"llm_ms": 1.0},
            retrieval_results=[],
        )
