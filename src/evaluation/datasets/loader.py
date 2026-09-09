import json
from pathlib import Path
from typing import Any

from src.core.models import EvaluationSample


class DatasetLoadError(Exception):
    pass


def load_dataset(path: str) -> list[EvaluationSample]:
    p = Path(path)
    if not p.exists():
        raise DatasetLoadError(f"Dataset file not found: {path}")

    text = p.read_text(encoding="utf-8")
    raw: Any
    if p.suffix.lower() == ".jsonl":
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        raw = json.loads(text)
        if isinstance(raw, dict):
            raw = raw.get("samples", raw.get("queries", []))

    if not isinstance(raw, list):
        raise DatasetLoadError("Dataset must be a JSON array or object with 'samples'/'queries' list")

    samples: list[EvaluationSample] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        try:
            sample = EvaluationSample(
                query=item.get("query") or item.get("question") or "",
                relevant_document_ids=item.get("relevant_document_ids", []),
                relevant_chunk_ids=item.get("relevant_chunk_ids", []),
                expected_answer=item.get("expected_answer", item.get("answer", "")),
                difficulty=item.get("difficulty", "medium"),
                category=item.get("category", "general"),
                metadata=item.get("metadata", {}),
            )
        except Exception as exc:
            raise DatasetLoadError(f"Invalid sample at index {idx}: {exc}") from exc
        samples.append(sample)
    return samples


def save_dataset(samples: list[EvaluationSample], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for sample in samples:
        data.append(
            {
                "query": sample.query,
                "relevant_document_ids": sample.relevant_document_ids,
                "relevant_chunk_ids": sample.relevant_chunk_ids,
                "expected_answer": sample.expected_answer,
                "difficulty": sample.difficulty,
                "category": sample.category,
                "metadata": sample.metadata,
            }
        )
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
