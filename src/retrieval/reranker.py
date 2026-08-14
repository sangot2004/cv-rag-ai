import logging

from sentence_transformers import CrossEncoder

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """Lazy load — model khá nặng (vài trăm MB), chỉ tải khi thực sự cần
    rerank, không tải lúc import module (tránh làm chậm mọi task khác dùng
    chung Celery worker process).

    QUAN TRỌNG: dùng bản đa ngôn ngữ (mmarco), KHÔNG dùng
    'cross-encoder/ms-marco-MiniLM-*' mặc định — bản đó chỉ mạnh tiếng Anh,
    sẽ rerank sai lệch âm thầm với câu hỏi/CV tiếng Việt mà không báo lỗi gì.
    """

    global _model
    if _model is None:
        _model = CrossEncoder(settings.RERANK_MODEL)
    return _model


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """candidates: list dict có key 'payload' chứa 'chunk_text'.
    Trả lại list đã sắp xếp lại theo điểm rerank thật (thay 'combined_score'
    của hybrid_search bằng 'rerank_score' chính xác hơn), cắt còn top_k.
    """
    if not candidates:
        return []

    pairs = [(query, c["payload"].get("chunk_text", "")) for c in candidates]
    scores = _get_model().predict(pairs)

    for c, score in zip(candidates, scores):
        c["rerank_score"] = float(score)

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
    logger.info("rerank query=%r: %d candidates -> top %d", query, len(candidates), len(ranked))
    return ranked
