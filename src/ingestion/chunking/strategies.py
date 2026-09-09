from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from src.core.models import Chunk, Document


@dataclass
class ChunkingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 64
    strategy: str = "fixed"
    separator: str = "\n"


def _split_fixed(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - chunk_overlap
        if start >= len(text):
            break
    return [c for c in chunks if c.strip()]


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _split_sentence(text: str) -> list[str]:
    return _split_sentences(text)


def _split_paragraph(text: str) -> list[str]:
    return _split_paragraphs(text)


def _split_recursive(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    paragraphs = _split_paragraphs(text)
    if len(paragraphs) == 1:
        sentences = _split_sentences(text)
        if len(sentences) == 1 or all(len(s) > chunk_size for s in sentences):
            return _split_fixed(text, chunk_size, chunk_overlap)

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            if current_len + len(sentence) + 1 > chunk_size and current:
                chunk_text = " ".join(current)
                if chunk_text.strip():
                    chunks.append(chunk_text)
                overlap_len = 0
                overlap_sentences: list[str] = []
                for s in reversed(current):
                    if overlap_len + len(s) + 1 <= chunk_overlap:
                        overlap_len += len(s) + 1
                        overlap_sentences.insert(0, s)
                    else:
                        break
                current = overlap_sentences + [sentence]
                current_len = sum(len(s) for s in current) + max(len(current) - 1, 0)
            else:
                current.append(sentence)
                current_len += len(sentence) + (1 if current_len > 0 else 0)
        if current:
            chunk_text = " ".join(current)
            if chunk_text.strip():
                chunks.append(chunk_text)
        return [c for c in chunks if c.strip()]

    chunks = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if current_len + len(paragraph) + 2 > chunk_size and current:
            chunk_text = "\n\n".join(current)
            if chunk_text.strip():
                chunks.append(chunk_text)
            overlap_len = 0
            overlap_paragraphs: list[str] = []
            for p in reversed(current):
                if overlap_len + len(p) + 2 <= chunk_overlap:
                    overlap_len += len(p) + 2
                    overlap_paragraphs.insert(0, p)
                else:
                    break
            current = overlap_paragraphs + [paragraph]
            current_len = sum(len(p) for p in current) + max(len(current) - 1, 0) * 2
        else:
            current.append(paragraph)
            current_len += len(paragraph) + (2 if current_len > 0 else 0)
    if current:
        chunk_text = "\n\n".join(current)
        if chunk_text.strip():
            chunks.append(chunk_text)
    return [c for c in chunks if c.strip()]


StrategyFn = Callable[[str, int, int], list[str]]


def get_strategy(strategy: str) -> StrategyFn:
    strategies: dict[str, StrategyFn] = {
        "fixed": _split_fixed,
        "sentence": lambda text, chunk_size, chunk_overlap: _split_fixed(
            "\n".join(_split_sentences(text)), chunk_size, chunk_overlap
        ),
        "paragraph": lambda text, chunk_size, chunk_overlap: _split_fixed(
            "\n\n".join(_split_paragraphs(text)), chunk_size, chunk_overlap
        ),
        "recursive": _split_recursive,
    }
    if strategy not in strategies:
        raise ValueError(
            f"Unknown chunking strategy: {strategy}. "
            f"Choose from {list(strategies.keys())}"
        )
    return strategies[strategy]


class Chunker:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        strategy: str = "fixed",
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self._splitter = get_strategy(strategy)

    def chunk(self, document: Document) -> list[Chunk]:
        texts = self._splitter(document.text, self.chunk_size, self.chunk_overlap)
        chunks: list[Chunk] = []
        for index, text in enumerate(texts):
            chunk_id = f"{document.document_id}_chunk_{index:04d}"
            chunk = Chunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                source=document.source,
                file_name=document.file_name,
                text=text,
                chunk_index=index,
                document_type=document.document_type,
                metadata={
                    **document.metadata,
                    "chunking_strategy": self.strategy,
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "total_chunks": len(texts),
                },
            )
            chunks.append(chunk)
        return chunks
