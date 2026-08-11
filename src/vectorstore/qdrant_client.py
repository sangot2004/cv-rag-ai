import logging


from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.config.settings import get_settings
logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection = settings.QDRANT_COLLECTION

    def ensure_collection(self) -> None:
        collections_response = self.client.get_collections().collections
        existing = [c.name for c in collections_response]
        if self.collection in existing:
            return

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="candidate_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="section_type",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        logger.info("Created Qdrant collection: %s (dim=%d)", self.collection, settings.EMBEDDING_DIM)

    def upsert_chunks(self, chunk_ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None:
        points = [
            PointStruct(id=cid, vector=vec, payload=payload)
            for cid, vec, payload in zip(chunk_ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def delete_by_candidate(self, candidate_id: str) -> None:
        """
        Dùng khi cần re-index 1 candidate - xoá hết point cũ trước khi ghi lại"""
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="candidate_id", match=MatchValue(value=candidate_id))]
            ),
        )
