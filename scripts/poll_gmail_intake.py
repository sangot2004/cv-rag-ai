"""
Chạy thử pipeline tiếp nhận CV qua email 1 lần.

Cách chạy (đầy đủ, cần MySQL đã chạy migration):
    python scripts/poll_gmail_intake.py

Cách chạy tạm (chưa có MySQL, chỉ test Gmail + validate + upload MinIO):
    python scripts/poll_gmail_intake.py --dry-run

Chạy định kỳ (dev, đơn giản nhất - cron mỗi 2 phút):
    */2 * * * * cd /path/to/cv-rag-ai && venv/bin/python scripts/poll_gmail_intake.py >> logs/intake.log 2>&1

Sau này thay bằng Celery beat task nếu cần tích hợp vào queue chung.
"""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from src.ingestion.email_intake.intake_pipeline import EmailIntakePipeline  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Bỏ qua ghi MySQL, chỉ test Gmail/validate/MinIO"
    )
    args = parser.parse_args()

    pipeline = EmailIntakePipeline(dry_run=args.dry_run)
    stats = pipeline.run_once()
    logging.info("Intake run finished (dry_run=%s): %s", args.dry_run, stats)


if __name__ == "__main__":
    main()
