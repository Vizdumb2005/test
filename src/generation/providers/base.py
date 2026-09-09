from typing import Protocol, runtime_checkable, Any

from src.core.models import Chunk, GeneratedAnswer


@runtime_checkable
class LLMProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        context: list[Chunk],
        **kwargs: Any,
    ) -> GeneratedAnswer:
        ...
