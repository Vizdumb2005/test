from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pypdf import PdfReader

from .base import BaseLoader
from src.core.models import Document


class PdfLoader(BaseLoader):
    document_type = "pdf"

    def __init__(
        self,
        metadata: Optional[dict[str, Any]] = None,
        extract_images: bool = False,
    ) -> None:
        super().__init__(metadata=metadata)
        self.extract_images = extract_images

    def _load(self, source: str) -> Document:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {source}")

        reader = PdfReader(str(path))
        pages_text: list[tuple[int, str]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages_text.append((page_number, text))

        full_text = "\n\n".join(text for _, text in pages_text)
        document_id = f"pdf_{path.stem}_{hash(path) & 0xFFFFFFFF:X}"

        return Document(
            document_id=document_id,
            source=str(path.resolve()),
            file_name=path.name,
            document_type=self.document_type,
            text=full_text,
            metadata={
                "page_count": len(reader.pages),
                "pages_with_text": sum(1 for _, t in pages_text if t.strip()),
                "extract_images": self.extract_images,
                **self.metadata,
            },
            page_count=len(reader.pages),
        )
