from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader
from src.core.models import Document


class TextLoader(BaseLoader):
    document_type = "text"

    def __init__(
        self,
        metadata: Optional[dict[str, Any]] = None,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> None:
        super().__init__(metadata=metadata)
        self.encoding = encoding
        self.errors = errors

    def _load(self, source: str) -> Document:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {source}")

        text = path.read_text(encoding=self.encoding, errors=self.errors)
        document_id = f"text_{path.stem}_{hash(path) & 0xFFFFFFFF:X}"

        return Document(
            document_id=document_id,
            source=str(path.resolve()),
            file_name=path.name,
            document_type=self.document_type,
            text=text,
            metadata={
                "encoding": self.encoding,
                "size_bytes": path.stat().st_size,
                "line_count": text.count("\n") + 1,
                **self.metadata,
            },
        )
