from __future__ import annotations

import abc
import hashlib
from pathlib import Path
from typing import Any, Optional

from src.core.models import Document


class BaseLoader(abc.ABC):
    document_type: str = "unknown"

    def __init__(self, metadata: Optional[dict[str, Any]] = None) -> None:
        self.metadata = metadata or {}

    @abc.abstractmethod
    def load(self, source: str) -> Document:
        raise NotImplementedError

    def _generate_document_id(self, source: str) -> str:
        content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        return f"doc_{content_hash}"

    def _file_name_from_source(self, source: str) -> str:
        return Path(source).name

    def load(self, source: str) -> Document:
        document = self._load(source)
        document.document_id = document.document_id or self._generate_document_id(source)
        document.file_name = document.file_name or self._file_name_from_source(source)
        document.document_type = document.document_type or self.document_type
        document.metadata = {**self.metadata, **document.metadata}
        return document

    @abc.abstractmethod
    def _load(self, source: str) -> Document:
        raise NotImplementedError
