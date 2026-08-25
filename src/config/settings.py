import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    MYSQL_CONN: str = os.getenv(
        "MYSQL_CONN",
        "mysql+pymysql://cvrag_app:cvrag_app_pass@localhost:3306/cv_rag_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "cv_chunks")

    # MINIO
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "cv-rag-files")
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
    CV_MIN_FILE_SIZE_BYTES: int = int(os.getenv("CV_MIN_FILE_SIZE_BYTES", 20*1024))  # 20KB
    CV_MAX_FILE_SIZE_BYTES: int = int(os.getenv("CV_MAX_FILE_SIZE_BYTES", 50*1024*1024))  # 50MB
    CV_MAX_PAGES: int = int(os.getenv("CV_MAX_PAGES", 10))  # 10 pages
    CV_MIN_TEXT_LENGTH: int = int(os.getenv("CV_MIN_TEXT_LENGTH", 100))
    CV_CLASSIFY_MIN_CONFIDENCE: float = float(os.getenv("CV_CLASSIFY_MIN_CONFIDENCE", 0.6))

    DEDUPE_MESSAGE_TTL_SECONDS: int = int(os.getenv("DEDUPE_MESSAGE_TTL_SECONDS", 7*24*3600))

    # gemini- dùng cả llm extract và embedding
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_LLM_MODEL: str = os.getenv("GEMINI_LLM_MODEL", "gemini-3.5-flash")
    GEMINI_CLASSIFY_MODEL: str = os.getenv("GEMINI_CLASSIFY_MODEL", 'gemini-3.5-flash-lite')
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", 768))

    @property
    def GOOGLE_API_KEYS(self) -> list[str]:
        keys = []
        if self.GOOGLE_API_KEY:
            keys.append(self.GOOGLE_API_KEY)
        i = 2
        while True:
            key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if not key:
                break
            keys.append(key)
            i += 1
        return keys

    # Rerank - cross-encoder self-host
    RERANK_MODEL: str = os.getenv("RERANK_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
