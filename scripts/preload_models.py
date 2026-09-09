import argparse
import sys

import structlog

from src.core.config import settings

logger = structlog.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Pre-download Hugging Face models for benchmark")
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device for models (cpu/cuda). Auto-detected if not set.",
    )
    args = parser.parse_args()

    device = args.device
    if device is None:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    logger.info("Pre-downloading models", device=device)

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Downloading embedding model", model=settings.embedding_model)
        model = SentenceTransformer(settings.embedding_model, device=device)
        logger.info("Embedding model downloaded", model=settings.embedding_model, dimension=model.get_sentence_embedding_dimension())
    except Exception as exc:
        logger.error("Failed to download embedding model", error=str(exc))
        return 1

    try:
        from sentence_transformers import CrossEncoder
        logger.info("Downloading reranker model", model=settings.reranker_model)
        reranker = CrossEncoder(settings.reranker_model, device=device)
        logger.info("Reranker model downloaded", model=settings.reranker_model)
    except Exception as exc:
        logger.error("Failed to download reranker model", error=str(exc))
        return 1

    print("All models pre-downloaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
