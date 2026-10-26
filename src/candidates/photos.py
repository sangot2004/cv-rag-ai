"""Read a stored portrait after verifying the current account's permission."""
from minio.error import S3Error
from sqlalchemy import select
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import HTTPError

from src.candidates.service import visibility_conditions
from src.candidates.errors import CandidateNotFound, CandidatePhotoNotFound
from src.chat.errors import DependencyUnavailable
from src.db import session as db_session
from src.db.models import Candidate
from src.storage.minio_client import MinioStorage


def get_candidate_photo(candidate_id: str) -> tuple[bytes, str]:
    conditions = visibility_conditions()
    with db_session.SessionLocal() as session:
        row = session.execute(select(Candidate.photo_object_key).where(
            Candidate.candidate_id == candidate_id, *conditions)).one_or_none()
    if row is None:
        raise CandidateNotFound()
    if not row.photo_object_key:
        raise CandidatePhotoNotFound()

    # GET must not create buckets. Bound connection/read retries for this
    # optional UI resource; storage failures must not block the candidate list.
    http = PoolManager(timeout=Timeout(connect=3, read=10), retries=Retry(total=1, backoff_factor=0))
    try:
        data = MinioStorage(ensure_bucket=False, http_client=http).download_bytes(row.photo_object_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
            raise CandidatePhotoNotFound() from exc
        raise DependencyUnavailable() from exc
    except (HTTPError, OSError) as exc:
        raise DependencyUnavailable() from exc
    finally:
        http.clear()

    # Serve raster images only, regardless of the object's extension/metadata.
    # The ingestion pipeline currently saves JPEG portraits.
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "image/webp"
    raise CandidatePhotoNotFound()
