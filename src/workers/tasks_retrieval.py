import logging

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.workers.tasks_retrieval.refresh_bm25_index")
def refresh_bm25_index() -> dict:
    """Build lại BM25 index từ toàn bộ chunk trong Qdrant, lưu vào Redis.
    Chạy định kỳ qua Celery Beat (xem beat_schedule trong celery_app.py) +
    1 lần ngay khi worker khởi động (qua on_after_configure ở celery_app.py).
    """
    from src.retrieval.bm25_index import build_and_store_index

    count = build_and_store_index()
    logger.info("refresh_bm25_index xong: %d chunk", count)
    return {"chunks_indexed": count}
