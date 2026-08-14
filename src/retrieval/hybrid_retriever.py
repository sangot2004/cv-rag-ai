import logging

from src.ingestion.embedding.embedder import embed_query
from src.retrieval.bm25_index import search_bm25
from src.vectorstore.qdrant_client import QdrantStore

logger = logging.getLogger(__name__)


def _normalize_scores(results: list[dict]) -> list[dict]:
    """BM25 score và cosine similarity (Qdrant) có thang điểm khác hẳn nhau
    (BM25 có thể ra vài chục, cosine luôn 0-1) — phải normalize về cùng
    thang [0, 1] trước khi cộng gộp, không thì 1 bên sẽ luôn át bên kia.
    """

    if not results:
        return results
    scores = [r["score"] for r in results]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    for r in results:
        r["norm_score"] = (r["score"] - lo) / span if span > 0 else 1.0
    return results


def hybrid_search(
        query: str,
        top_k: int = 10,
        candidate_id: str | None = None,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
) -> list[dict]:
    """Gộp kết quả BM25 (từ khóa, tốt cho tên riêng/thuật ngữ chính xác) và
    Vector search (ngữ nghĩa, tốt cho câu hỏi diễn giải tự nhiên).
    vector_weight cao hơn mặc định vì embedding thường cho kết quả liên
    quan hơn với câu hỏi tự nhiên của HR — có thể tune lại sau khi có dữ
    liệu đánh giá thật (Luồng E).

    Tự viết merge thay vì dùng LangChain EnsembleRetriever, vì BM25 giờ
    build định kỳ qua Celery (không phải BM25Retriever.from_documents() tại
    chỗ theo interface BaseRetriever chuẩn của LangChain).
    """
    query_vector = embed_query(query)
    vector_results = QdrantStore().search(query_vector, top_k=top_k * 2, candidate_id=candidate_id)
    bm25_results = search_bm25(query, top_k=top_k * 2)

    if candidate_id:
        bm25_results = [r for r in bm25_results if r["payload"].get("candidate_id") == candidate_id]

    vector_results = _normalize_scores(vector_results)
    bm25_results = _normalize_scores(bm25_results)

    merged: dict[str, dict] = {}
    for r in vector_results:
        merged[r["chunk_id"]] = {
            "chunk_id": r["chunk_id"],
            "payload": r["payload"],
            "combined_score": r["norm_score"] * vector_weight,
        }
    for r in bm25_results:
        if r["chunk_id"] in merged:
            merged[r["chunk_id"]]["combined_score"] += r["norm_score"] * bm25_weight
        else:
            merged[r["chunk_id"]] = {
                "chunk_id": r["chunk_id"],
                "payload": r["payload"],
                "combined_score": r["norm_score"] * bm25_weight,
            }

    ranked = sorted(merged.values(), key=lambda x: x["combined_score"], reverse=True)[:top_k]
    logger.info(
        "hybrid_search query=%r ->%d vector + %d bm25 -> %d merged",
        query, len(vector_results), len(bm25_results), len(ranked),
    )
    return ranked
