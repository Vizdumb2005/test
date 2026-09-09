from typing import Any, Optional

from src.core.models import RetrievalResult


class RagasEvaluator:
    def __init__(
        self,
        llm_provider: Optional[Any] = None,
        embeddings: Optional[Any] = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.embeddings = embeddings
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            import ragas  # noqa: F401
            from ragas.metrics import (  # noqa: F401
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        return self._available

    def evaluate(
        self,
        queries: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if not self._available:
            return {
                "available": False,
                "error": "ragas is not installed. Install with: pip install ragas",
                "scores": {},
            }

        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

            data = {
                "question": queries,
                "answer": answers,
                "contexts": contexts,
            }
            if ground_truths:
                data["ground_truth"] = ground_truths

            dataset = Dataset.from_dict(data)
            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            )

            scores = {}
            for metric_name in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
                if metric_name in result:
                    scores[metric_name] = float(result[metric_name].mean()) if hasattr(result[metric_name], "mean") else float(result[metric_name])

            return {
                "available": True,
                "scores": scores,
                "raw": result.to_dict() if hasattr(result, "to_dict") else str(result),
            }
        except Exception as exc:
            return {
                "available": True,
                "error": str(exc),
                "scores": {},
            }

    def evaluate_retrieval_results(
        self,
        queries: list[str],
        results: list[list[RetrievalResult]],
        ground_truths: Optional[list[list[str]]] = None,
    ) -> dict[str, Any]:
        if not self._available:
            return {
                "available": False,
                "error": "ragas is not installed",
                "scores": {},
            }

        try:
            answers = ["" for _ in queries]
            contexts = [[r.text for r in result_list] for result_list in results]
            return self.evaluate(queries, answers, contexts, ground_truths)
        except Exception as exc:
            return {
                "available": True,
                "error": str(exc),
                "scores": {},
            }
