import os
from functools import lru_cache


class Settings:
    MYSQL_CONN: str = os.getenv(
        "MYSQL_CONN",
        "mysql+pymysql://cvrag_app:cvrag_app_pass@localhost:3306/cv_rag_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    # MINIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "cvrag-bucket")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Gmail intake
    GMAIL_CREDENTIALS_PATH: str = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    GMAIL_TOKEN_PATH: str = os.getenv("GMAIL_TOKEN_PATH", "token.json")
    GMAIL_POLL_QUERY: str = os.getenv(
        "GMAIL_POLL_QUERY",
        "is:unread has:attachment filename:pdf"
    )
    GMAIL_LABEL_PROCESSED: str = os.getenv("GMAIL_LABEL_PROCESSED", "CV-Processed")

    # Validate rules - quy ước tên file: HoTen_ViTriUngTuyen_CV.pdf
    CV_FILENAME_PATTERN: str = os.getenv(
        "CV_FILENAME_PATTERN", r"^[A-Za-zÀ-ỹ]+_[A-Za-z0-9]+_CV\.pdf$"
    )
    CV_MIN_FILE_SIZE_BYTES: int = int(os.getenv("CV_MIN_FILE_SIZE_BYTES", 50*1024))  # 50KB
    CV_MAX_FILE_SIZE_BYTES: int = int(os.getenv("CV_MAX_FILE_SIZE_BYTES", 5*1024*1024))  # 5MB
    CV_MAX_PAGES: int = int(os.getenv("CV_MAX_PAGES", 10))  # 10 pages

    DEDUPE_MESSAGE_TTL_SECONDS: int = int(os.getenv("DEDUPE_MESSAGE_TTL_SECONDS", 7*24*3600))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
