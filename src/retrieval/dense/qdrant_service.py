import logging
import uuid
from typing import Any, Optional

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import ResponseHandlingException

from src.core.config import settings

logger = structlog.get_logger("qdrant_service")


class QdrantService:
    def __init__(
        self,
        url: Optional[str] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        recreate: bool = False,
    ) -> None:
        self.url = url or settings.qdrant_url
        self.collection_name = collection_name or settings.qdrant_collection
        self.vector_size = vector_size or settings.qdrant_vector_size
        self._client: Optional[QdrantClient] = None
        self._recreate = recreate

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self.url, check_compatibility=False)
            self._ensure_collection(recreate=self._recreate)
        return self._client

    def _ensure_collection(self, recreate: bool = False) -> None:
        try:
            existing = self.client.get_collection(self.collection_name)
            if recreate:
                logger.info("recreating_collection", collection=self.collection_name)
                self.client.delete_collection(self.collection_name)
                self._create_collection()
            else:
                if int(existing.config.params.vectors.size) != self.vector_size:
                    logger.warning(
                        "vector_size_mismatch",
                        collection=self.collection_name,
                        expected=self.vector_size,
                        actual=int(existing.config.params.vectors.size),
                    )
                logger.debug("collection_exists", collection=self.collection_name)
        except (ResponseHandlingException, Exception):
            logger.info("creating_collection", collection=self.collection_name, vector_size=self.vector_size)
            self._create_collection()

    def _create_collection(self) -> None:
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=rest.VectorParams(size=self.vector_size, distance=rest.Distance.COSINE),
        )

    def _resolve_point_id(self, chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

    def upsert(
        self,
        points: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> None:
        if not points:
            return

        logger.debug("upserting_points", collection=self.collection_name, count=len(points))
        qdrant_points = []
        for point in points:
            point_id = self._resolve_point_id(point["chunk_id"])
            qdrant_points.append(
                rest.PointStruct(
                    id=point_id,
                    vector=point["vector"],
                    payload={
                        "chunk_id": point["chunk_id"],
                        "document_id": point.get("document_id", ""),
                        "text": point.get("text", ""),
                        "source": point.get("source", ""),
                        "file_name": point.get("file_name", ""),
                        "chunk_index": point.get("chunk_index", 0),
                        "document_type": point.get("document_type", "unknown"),
                        **point.get("metadata", {}),
                    },
                )
            )

        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
        logger.info("upsert_complete", collection=self.collection_name, count=len(qdrant_points))

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_conditions: Optional[rest.Filter] = None,
        score_threshold: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        logger.debug("searching_collection", collection=self.collection_name, top_k=top_k)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        formatted = []
        for hit in results.points:
            payload = hit.payload or {}
            formatted.append(
                {
                    "chunk_id": str(payload.get("chunk_id", hit.id)),
                    "document_id": str(payload.get("document_id", "")),
                    "text": str(payload.get("text", "")),
                    "score": float(hit.score),
                    "source": str(payload.get("source", "")),
                    "file_name": str(payload.get("file_name", "")),
                    "chunk_index": int(payload.get("chunk_index", 0)),
                    "document_type": str(payload.get("document_type", "unknown")),
                    "metadata": {k: v for k, v in payload.items() if k not in {"chunk_id", "document_id", "text", "source", "file_name", "chunk_index", "document_type"}},
                }
            )
        return formatted

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        logger.debug("deleting_points", collection=self.collection_name, count=len(chunk_ids))
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(points=chunk_ids),
        )
        logger.info("delete_complete", collection=self.collection_name, count=len(chunk_ids))

    def delete_by_filter(self, filter_condition: rest.Filter) -> int:
        result = self.client.delete(collection_name=self.collection_name, points_selector=filter_condition)
        logger.info("delete_by_filter_complete", collection=self.collection_name, deleted=result)
        return result

    def count(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return int(info.points_count)
