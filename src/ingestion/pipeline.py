from __future__ import annotations

import uuid
from typing import Any, Optional

from src.core.models import Chunk, Document
from src.ingestion.chunking.strategies import Chunker, ChunkingConfig
from src.ingestion.loaders.base import BaseLoader
from src.ingestion.preprocessing.cleaner import TextCleaner


class IngestionPipeline:
    def __init__(
        self,
        loader: Optional[BaseLoader] = None,
        cleaner: Optional[TextCleaner] = None,
        chunker: Optional[Chunker] = None,
        default_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.loader = loader
        self.cleaner = cleaner or TextCleaner()
        self.chunker = chunker or Chunker()
        self.default_metadata = default_metadata or {}

    def ingest(self, source: str, metadata: Optional[dict[str, Any]] = None) -> list[Chunk]:
        document = self.loader.load(source) if self.loader else self._load_document(source)
        document.metadata = {**self.default_metadata, **document.metadata, **(metadata or {})}

        cleaned_text = self.cleaner.clean(document.text)
        document.text = cleaned_text
        document.metadata["text_length"] = len(cleaned_text)
        document.metadata["char_count"] = len(cleaned_text)

        chunks = self.chunker.chunk(document)
        return chunks

    def _load_document(self, source: str) -> Document:
        from src.ingestion.loaders.pdf_loader import PdfLoader
        from src.ingestion.loaders.text_loader import TextLoader
        from src.ingestion.loaders.markdown_loader import MarkdownLoader
        from src.ingestion.loaders.docx_loader import DocxLoader

        suffix = source.lower().split("?")[0].rsplit(".", 1)[-1] if "." in source else "text"
        mapping = {
            "pdf": PdfLoader,
            "txt": TextLoader,
            "md": MarkdownLoader,
            "markdown": MarkdownLoader,
            "docx": DocxLoader,
            "doc": DocxLoader,
        }
        loader_cls = mapping.get(suffix, TextLoader)
        loader = loader_cls()
        return loader.load(source)
