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

    def search(
        self, query_vector: list[float], top_k: int = 10, candidate_id: str | None = None
    ) -> list[dict]:
        """vector search - trả list dict{ chunk_id, score, payload} để dễ merge
        với bm25 ở tầng hybrid_retriever"""
        query_filter = None
        if candidate_id:
            query_filter = Filter(
                must=[FieldCondition(key="candidate_id", match=MatchValue(value=candidate_id))]
            )

        result = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {"chunk_id": str(point.id), "score": point.score, "payload": point.payload}
            for point in result.points
        ]

    def fetch_all_chunks(self, batch_size: int = 200) -> list[dict]:
        """Lấy toàn bộ chunk (id + payload) trong collection — dùng để build
        BM25 index định kỳ (bước 2 trong Giai đoạn 3), vì text của chunk chỉ
        lưu ở Qdrant payload, MySQL không lưu chunk_text.
        """
        all_chunks = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_chunks.extend(
                {"chunk_id": str(p.id), "payload": p.payload} for p in points
            )
            if offset is None:
                break
        return all_chunks
