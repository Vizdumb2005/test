import asyncio
import argparse
import sys
from pathlib import Path
from src.core.logging import logger
from src.core.config import settings
from src.ingestion.pipeline import IngestionPipeline


async def ingest_path(path: str):
    pipeline = IngestionPipeline()
    sources = []
    path_obj = Path(path)

    if path_obj.is_file():
        sources.append(str(path_obj))
    elif path_obj.is_dir():
        for ext in ["*.pdf", "*.txt", "*.md", "*.docx"]:
            sources.extend([str(p) for p in path_obj.glob(f"**/{ext}")])
    else:
        logger.error("Path does not exist", path=path)
        sys.exit(1)

    if not sources:
        logger.error("No supported files found", path=path)
        sys.exit(1)

    logger.info("Found files to ingest", count=len(sources))

    total_chunks = 0
    for source in sources:
        try:
            chunks = pipeline.ingest(source)
            total_chunks += len(chunks)
            logger.info("Ingested", source=source, chunks=len(chunks))
        except Exception as e:
            logger.error("Failed to ingest", source=source, error=str(e))

    logger.info("Ingestion complete", total_chunks=total_chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG system")
    parser.add_argument("path", help="Path to file or directory")
    args = parser.parse_args()
    asyncio.run(ingest_path(args.path))


if __name__ == "__main__":
    main()
