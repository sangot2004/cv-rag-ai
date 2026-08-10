import logging

from src.db.models import IngestionJob
from src.db.session import SessionLocal
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.workers.tasks_ingestion.poll_email_intake")
def poll_email_intake() -> dict:
    "chạy định kỳ qua celery beat"
    from src.ingestion.email_intake.intake_pipeline import EmailIntakePipeline

    pipeline = EmailIntakePipeline(dry_run=False)
    stats = pipeline.run_once()
    logger.info("poll_email_intake finished; %s", stats)
    return stats


@celery_app.task(
    name="src.workers.tasks_ingestion.process_cv_job",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def process_cv_job(self, job_id: str) -> None:
    """
    Entry point của Luồng A (Parsing & Extraction) — được dispatch tự động
    ngay sau khi EmailIntakePipeline ghi xong ingestion_jobs (status='pending').

    ĐANG LÀ PLACEHOLDER: mới nối được dây dispatch job_id -> Celery queue,
    logic parse/extract thật (A2-A9 trong worklog) chưa code — thuộc
    Giai đoạn 2, làm sau. Hiện task chỉ xác nhận nhận được job và cập nhật
    status='parsing' để đánh dấu đã vào hàng đợi xử lý, tránh job nằm mãi
    ở 'pending' không ai biết có bị nhặt lên hay chưa.
    """

    logger.info("process_cv_job received job_id=%s (parsing chưa implement)", job_id)

    with SessionLocal() as session:
        job = session.get(IngestionJob, job_id)
        if job is None:
            logger.error("job_id=%s không tồn tại trong ingestion_jobs", job_id)
            return

        job.status = "parsing"
        session.commit()

    # TODO (Giai đoạn 2 — Luồng A):
    #   A3 load file từ MinIO -> A4 parse (PyMuPDF/python-docx) -> A5 check text hợp lệ
    #   -> A5b validate nội dung có phải CV -> A5c check content_hash trùng
    #   -> A6 LLM structured extraction -> A7 validate schema -> A8 update status
    #   Xem chi tiết bảng Luồng A trong worklog.
