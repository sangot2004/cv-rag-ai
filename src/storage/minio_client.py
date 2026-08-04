import io
import logging
from datetime import datetime

from minio import Minio
from minio.error import S3Error

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MinioStorage:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Ensure the bucket exists, create it if it doesn't."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("created MINIO bucket: %s", self.bucket)
        except S3Error as e:
            logger.error("Error checking/creating bucket: %s", e)
            raise

    @staticmethod
    def build_object_key(candidate_ref: str, filename: str) -> str:
        now = datetime.utcnow()
        return f"{now.year:04d}/{now.month:02d}/{candidate_ref}/{filename}"

    def upload_bytes(self, object_key: str, data: bytes, content_type: str = "application/pdf") -> str:
        self.client.put_object(
            self.bucket,
            object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("Uploaded %s (%d bytes) to bucket %s", object_key, len(data), self.bucket)
        return object_key

    def download_bytes(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def object_exists(self, object_key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_key)
            return True
        except S3Error as e:
            return False
