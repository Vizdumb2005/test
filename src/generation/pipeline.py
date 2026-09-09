import logging
from typing import Any

from src.core.config import settings
from src.core.models import (
    Chunk,
    GeneratedAnswer,
    QueryResult,
    RetrievalResult,
)
from src.generation.prompts.templates import (
    CITATION_PROMPT_TEMPLATE,
    FEW_SHOT_TEMPLATE,
    SUMMARIZATION_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
    _FEW_SHOT_EXAMPLE,
)
from src.generation.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class GenerationPipeline:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def build_prompt(
        self,
        query: str,
        context: list[Chunk],
        template_name: str = "default",
        **kwargs: Any,
    ) -> str:
        if not context:
            return f"You are an enterprise assistant. Question: {query}"

        ctx = self._format_context(context)
        if template_name == "citation":
            return CITATION_PROMPT_TEMPLATE.format(context=ctx, query=query, **kwargs)
        if template_name == "summarization":
            return SUMMARIZATION_PROMPT_TEMPLATE.format(context=ctx, query=query, **kwargs)
        if template_name == "few_shot":
            return FEW_SHOT_TEMPLATE.format(
                few_shot=_FEW_SHOT_EXAMPLE, context=ctx, query=query, **kwargs
            )
        return USER_PROMPT_TEMPLATE.format(context=ctx, query=query, **kwargs)

    def construct_context(
        self,
        retrieval_results: list[RetrievalResult],
        max_chunks: int | None = None,
        max_characters: int | None = None,
    ) -> list[Chunk]:
        max_chunks = max_chunks or settings.context_max_chunks
        max_characters = max_characters or settings.context_max_characters

        seen_ids: set[str] = set()
        unique_chunks: list[Chunk] = []
        total_chars = 0

        for result in retrieval_results:
            if result.chunk_id in seen_ids:
                continue
            seen_ids.add(result.chunk_id)

            chunk = Chunk(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                source=result.metadata.get("source", ""),
                file_name=result.metadata.get("file_name", ""),
                text=result.text,
                chunk_index=result.metadata.get("chunk_index", 0),
                page_number=result.metadata.get("page_number"),
                section=result.metadata.get("section"),
                document_type=result.metadata.get("document_type", "unknown"),
                metadata=result.metadata,
            )
            chunk_len = len(chunk.text)
            if total_chars + chunk_len > max_characters:
                break
            unique_chunks.append(chunk)
            total_chars += chunk_len
            if len(unique_chunks) >= max_chunks:
                break

        return unique_chunks

    async def generate(
        self,
        query_result: QueryResult,
        template_name: str = "default",
        **kwargs: Any,
    ) -> GeneratedAnswer:
        context = self.construct_context(query_result.results)
        prompt = self.build_prompt(query_result.query, context, template_name=template_name)
        answer = await self.provider.generate(prompt, context, **kwargs)
        return answer

    def _format_context(self, chunks: list[Chunk]) -> str:
        parts = []
        for i, chunk in enumerate(chunks):
            source = chunk.source or chunk.file_name or "unknown"
            parts.append(f"[{i + 1}] Source: {source}\n{chunk.text}")
        return "\n\n".join(parts)
