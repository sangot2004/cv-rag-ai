from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "cv-rag-ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.workers.tasks_ingestion",
        "src.workers.tasks_retrieval",
        "src.workers.tasks_notification",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    # Retry mặc định mọi task nếu không override riêng
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


celery_app.conf.beat_schedule = {
    "pool-gmail-intake-every-2-minutes": {
        "task": "src.workers.tasks_ingestion.poll_email_intake",
        "schedule": crontab(minute="*/5")
    },
    "refresh-bm25-index-every-15-minutes": {
        "task": "src.workers.tasks_retrieval.refresh_bm25_index",
        "schedule": crontab(minute="*/15"),
    },
}


@worker_ready.connect
def _build_bm25_index_on_startup(**kwargs):
    """Build BM25 index ngay khi Worker khởi động — theo đúng quyết định
    'build 1 lần lúc start + refresh định kỳ', không đợi tới lần beat đầu
    tiên (có thể mất tới 15 phút nếu chỉ dựa vào beat_schedule).
    """
    from src.workers.tasks_retrieval import refresh_bm25_index

    refresh_bm25_index.delay()
