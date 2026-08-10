from celery import Celery
from celery.schedules import crontab

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "cv-rag-ai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.workers.tasks_ingestion",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accep_content=["json"],
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
        "schedule": crontab(minute="*/2")
    },
}
