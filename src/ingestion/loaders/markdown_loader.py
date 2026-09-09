from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from markdown import markdown
from bs4 import BeautifulSoup

from .base import BaseLoader
from src.core.models import Document


class MarkdownLoader(BaseLoader):
    document_type = "markdown"

    def __init__(
        self,
        metadata: Optional[dict[str, Any]] = None,
        encoding: str = "utf-8",
        strip_html: bool = True,
    ) -> None:
        super().__init__(metadata=metadata)
        self.encoding = encoding
        self.strip_html = strip_html

    def _load(self, source: str) -> Document:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {source}")

        text = path.read_text(encoding=self.encoding)
        document_id = f"markdown_{path.stem}_{hash(path) & 0xFFFFFFFF:X}"

        processed_text = text
        if self.strip_html:
            html = markdown(text)
            processed_text = BeautifulSoup(html, "html.parser").get_text(
                separator="\n"
            )

        return Document(
            document_id=document_id,
            source=str(path.resolve()),
            file_name=path.name,
            document_type=self.document_type,
            text=processed_text,
            metadata={
                "encoding": self.encoding,
                "strip_html": self.strip_html,
                "size_bytes": path.stat().st_size,
                "original_length": len(text),
                "processed_length": len(processed_text),
                **self.metadata,
            },
        )
