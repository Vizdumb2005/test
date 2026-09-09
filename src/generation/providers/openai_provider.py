import logging
from typing import Any

import httpx

from src.core.config import settings
from src.core.models import Chunk, GeneratedAnswer
from src.generation.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def generate(
        self,
        prompt: str,
        context: list[Chunk],
        **kwargs: Any,
    ) -> GeneratedAnswer:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured")

        context_text = "\n\n".join(
            f"[{i + 1}] {chunk.text}" for i, chunk in enumerate(context)
        )

        system_prompt = (
            "You are an enterprise assistant. Answer the user's question using ONLY "
            "the provided context. If the answer is not in the context, say you do not "
            "know. Cite sources using the [n] notation where n corresponds to the "
            "context item number."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {prompt}",
            },
        ]

        temperature = kwargs.get("temperature", settings.llm_temperature)
        max_tokens = kwargs.get("max_tokens", settings.llm_max_tokens)

        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        import time
        start = time.perf_counter()
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OpenAI API error",
                extra={"status": exc.response.status_code, "body": exc.response.text},
            )
            raise
        except httpx.RequestError as exc:
            logger.error("OpenAI request failed", extra={"error": str(exc)})
            raise
        latency_ms = (time.perf_counter() - start) * 1000

        data = response.json()
        answer_text = data["choices"][0]["message"]["content"]

        citations = _extract_citations(answer_text, context)

        return GeneratedAnswer(
            query=prompt,
            answer=answer_text,
            citations=citations,
            confidence=0.9,
            latency_ms={"llm_ms": round(latency_ms, 2)},
            retrieval_results=[],
        )

    async def close(self) -> None:
        await self._client.aclose()


def _extract_citations(answer: str, context: list[Chunk]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, chunk in enumerate(context):
        marker = f"[{i + 1}]"
        if marker in answer:
            cid = chunk.chunk_id
            if cid not in seen:
                seen.add(cid)
                citations.append(
                    {
                        "chunk_id": cid,
                        "document_id": chunk.document_id,
                        "source": chunk.source,
                        "file_name": chunk.file_name,
                        "marker": marker,
                        "text": chunk.text[:200],
                    }
                )
    return citations
