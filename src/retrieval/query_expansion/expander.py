import json
from typing import Optional

import httpx
import structlog

from src.core.config import settings

logger = structlog.get_logger("query_expander")


class QueryExpander:
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        count: Optional[int] = None,
    ) -> None:
        self.model = model or settings.query_expansion_model
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.count = count if count is not None else settings.query_expansion_count

    def expand(self, query: str) -> list[str]:
        if not settings.query_expansion_enabled:
            return []

        if not self.api_key:
            logger.debug("query_expansion_fallback_local", query_length=len(query))
            return self._local_expand(query)

        try:
            return self._llm_expand(query)
        except Exception as exc:
            logger.warning("query_expansion_failed_fallback", error=str(exc), query_length=len(query))
            return self._local_expand(query)

    def _llm_expand(self, query: str) -> list[str]:
        system_prompt = (
            "You are a search query expansion assistant. Generate alternative search queries "
            "that cover different phrasings, synonyms, and related terms for the given query. "
            "Return ONLY a JSON array of strings with no additional text."
        )
        user_prompt = f"Generate {self.count} alternative search queries for: {query}"

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 256,
            },
            timeout=30.0,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        expansions = json.loads(content)
        if not isinstance(expansions, list):
            raise ValueError("LLM returned non-list expansion")

        expansions = [str(q) for q in expansions[: self.count]]
        logger.debug("query_expansion_llm", original_query=query, expansions=expansions)
        return expansions

    def _local_expand(self, query: str) -> list[str]:
        words = query.lower().split()
        expansions = []

        if len(words) >= 2:
            expansions.append(" ".join(words[::-1]))

        common_synonyms = {
            "how": ["ways to", "methods to", "guide to"],
            "what": ["explain", "describe", "define"],
            "why": ["reasons for", "causes of", "explanation of"],
            "best": ["top", "leading", "most popular"],
            "create": ["build", "make", "develop", "implement"],
            "use": ["utilize", "apply", "work with"],
            "fix": ["repair", "resolve", "troubleshoot"],
            "learn": ["study", "master", "understand"],
            "compare": ["contrast", "difference between", "vs"],
            "install": ["setup", "deploy", "configure"],
        }

        for word in words:
            if word in common_synonyms:
                for syn in common_synonyms[word][:2]:
                    new_query = query.lower().replace(word, syn)
                    if new_query not in expansions:
                        expansions.append(new_query)

        if not expansions:
            expansions.append(f"information about {query}")

        expansions = expansions[: self.count]
        logger.debug("query_expansion_local", original_query=query, expansions=expansions)
        return expansions
