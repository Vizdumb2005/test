from __future__ import annotations

import re
import unicodedata
from typing import Optional


class TextCleaner:
    def __init__(
        self,
        lowercase: bool = False,
        remove_extra_whitespace: bool = True,
        normalize_unicode: bool = True,
        remove_special_chars: bool = False,
        special_char_pattern: Optional[str] = None,
    ) -> None:
        self.lowercase = lowercase
        self.remove_extra_whitespace = remove_extra_whitespace
        self.normalize_unicode = normalize_unicode
        self.remove_special_chars = remove_special_chars
        self.special_char_pattern = re.compile(
            special_char_pattern or r"[^\w\s\.,;:!?\-\(\)\"\'\/\\@#\$%\^&\*\+\=<>\[\]\{\}]"
        )

    def clean(self, text: str) -> str:
        if not text:
            return text

        cleaned = text

        if self.normalize_unicode:
            cleaned = unicodedata.normalize("NFKC", cleaned)

        if self.remove_special_chars:
            cleaned = self.special_char_pattern.sub(" ", cleaned)

        if self.remove_extra_whitespace:
            cleaned = re.sub(r"[ \t]+", " ", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
            cleaned = cleaned.strip()

        if self.lowercase:
            cleaned = cleaned.lower()

        return cleaned
