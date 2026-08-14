import logging
import pickle
import re

import redis
from rank_bm25 import BM25Okapi

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

REDIS_KEY = "bm25:index:v1"


def _tokenize(text: str) -> list[str]:
    """tokenzie basic: lower + tách theo từ, giữ dấu tiêng việt,
    Không dùng thư viện NLP """
    text = text.lower()
    return re.findall(r"[\w\u00c0-\u1ef9]+", text)


def build_and_store_index() -> int:
    """Build bm25 từ toàn bộ chunk trong qdrant, serialize + lưu vào redis.
    gọi từ celery task refresh_bm25_index (chạy định kỳ + lúc wokrer start),
    """
    from src.vectorstore.qdrant_client import QdrantStore

    store = QdrantStore()
    chunks = store.fetch_all_chunks()

    if not chunks:
        logger.warning("Không có chunks nào trong Qdrant, bỏ qua build BM25")
        return 0
    chunk_ids = [c["chunk_id"] for c in chunks]
    texts = [c["payload"].get("chunk_text", "") for c in chunks]
    payloads = [c["payload"] for c in chunks]
    tokenized = [_tokenize(t) for t in texts]

    bm25 = BM25Okapi(tokenized)

    blob = pickle.dumps(
        {"bm25": bm25, "chunk_ids": chunk_ids, "payloads": payloads}
    )

    r = redis.from_url(settings.REDIS_URL)
    r.set(REDIS_KEY, blob)

    logger.info("Đã build BM25 index: %d chunk, lưu vào Redis key=%s", len(chunk_ids), REDIS_KEY)
    return len(chunk_ids)


def load_index() -> dict | None:
    """Đọc index đã build sẵn từ Redis — dùng ở query time, KHÔNG build lại.
    Trả None nếu chưa từng build (ví dụ hệ thống vừa khởi động lần đầu,
    Celery beat chưa kịp chạy task refresh) — tầng gọi (hybrid_retriever)
    phải tự xử lý trường hợp này, fallback về vector-only search.
    """
    r = redis.from_url(settings.REDIS_URL)
    blob = r.get(REDIS_KEY)
    if blob is None:
        logger.warning("Chưa có BM25 index trong redis - có thể chưa chạy refresh_bm25_index lần nào.")
        return None
    return pickle.loads(blob)


def search_bm25(query: str, top_k=10) -> list[dict]:
    """Search trên index đã load từ Redis, trả cùng format với QdrantStore.search()
    để dễ merge ở hybrid_retriever: {chunk_id, score, payload}.
    """
    index = load_index()
    if index is None:
        return []

    tokenized_query = _tokenize(query)
    scores = index["bm25"].get_scores(tokenized_query)
    ranked = sorted(
        zip(index["chunk_ids"], scores, index["payloads"]), key=lambda x: x[1], reverse=True
    )[:top_k]

    return [
        {"chunk_id": cid, "score": float(score), "payload": payload}
        for cid, score, payload in ranked
        if score > 0
    ]
