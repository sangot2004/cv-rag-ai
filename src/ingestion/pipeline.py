import hashlib
import logging
import uuid
from datetime import date, datetime

from src.config.settings import get_settings
from src.db.models import (
    Candidate,
    CandidateCertificate,
    CandidateChunk,
    CandidateEducation,
    CandidateExperience,
    CandidateProject,
    CandidateSkill,
    IngestionJob
)
from src.db.session import SessionLocal
from src.ingestion.chunking.document_builder import build_documents_from_cv
from src.ingestion.embedding.embedder import embed_texts
from src.ingestion.extraction.llm_extractor import classify_is_cv, extract_cv_data, ocr_extract_text_from_images
from src.ingestion.parsers.pdf_parser import (
    PdfParseError,
    extract_text_from_pdf,
    extract_portrait_photo,
    rasterize_pages,
)
from src.storage.minio_client import MinioStorage
from src.vectorstore.qdrant_client import QdrantStore

logger = logging.getLogger(__name__)
settings = get_settings()


class CVIngestionError(Exception):
    """Lỗi có thể retry được (khác với lỗi validate — bị reject thẳng, không retry)."""


class CVRejected(Exception):
    """Lỗi KHÔNG nên retry — bản chất file/nội dung sai, retry lại cũng vẫn sai."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    logger.warning("Không parse được date: %r — để None", date_str)
    return None


def run_ingestion_pipeline(job_id: str) -> str:
    storage = MinioStorage()

    with SessionLocal() as session:
        job = session.get(IngestionJob, job_id)
        if job is None:
            raise CVIngestionError(f"job_id={job_id} không tồn tại")

        # load file từ MinIO
        try:
            file_bytes = storage.download_bytes(job.minio_object_key)
        except Exception as e:
            raise CVIngestionError(f"Không tải được file từ MinIO: {e}") from e

        # parse
        try:
            raw_text = extract_text_from_pdf(file_bytes)
        except PdfParseError as e:
            raise CVRejected(f"corrupt_pdf: {e}")

        # check text hợp lệ, fallback OCR nếu nghi ngờ CV dạng scan/ảnh
        if len(raw_text) < settings.CV_MIN_TEXT_LENGTH:
            logger.info(
                "Text quá ngắn (%d ký tự) — nghi ngờ CV dạng scan, thử OCR qua Gemini vision",
                len(raw_text),
            )
            try:
                images = rasterize_pages(file_bytes)
                ocr_text = ocr_extract_text_from_images(images)
            except Exception as e:
                raise CVIngestionError(f"OCR fallback lỗi: {e}") from e

            if len(ocr_text) < settings.CV_MIN_TEXT_LENGTH:
                # Kể cả OCR cũng không ra đủ text -> thực sự không phải CV
                raise CVRejected("text_too_short_even_after_ocr")

            raw_text = ocr_text
            logger.info("OCR fallback thành công, %d ký tự", len(raw_text))

        # classify có phải CV không
        classification = classify_is_cv(raw_text)
        if not classification.is_cv or classification.confidence < settings.CV_CLASSIFY_MIN_CONFIDENCE:
            raise CVRejected(f"not_a_cv: {classification.reason}")

        # check trùng nội dung theo text hash
        text_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        existing = session.query(Candidate.candidate_id).filter(Candidate.content_hash == text_hash).first()
        if existing:
            raise CVRejected("duplicate_content_text_hash")

        # LLM structured extraction
        try:
            cv_data = extract_cv_data(raw_text)
        except Exception as e:
            raise CVIngestionError(f"LLM extraction lỗi: {e}") from e

        # validate schema
        if not cv_data.full_name:
            raise CVRejected("extraction_missing_full_name")

        # ghi candidates + bảng con
        candidate_id = str(uuid.uuid4())
        photo_object_key = None
        try:
            photo_bytes = extract_portrait_photo(file_bytes)
            if photo_bytes:
                photo_object_key = f"photos/{candidate_id}.jpg"
                storage.upload_bytes(photo_object_key, photo_bytes, content_type="image/jpeg")
                logger.info("Đã upload ảnh chân dung: %s", photo_object_key)
        except Exception:
            # Lỗi tách/upload ảnh KHÔNG được làm fail cả job — đây là tính
            # năng phụ (best-effort), CV vẫn xử lý bình thường không có ảnh.
            logger.exception("Lỗi khi tách/upload ảnh chân dung, bỏ qua (không chặn job)")

        candidate = Candidate(
            candidate_id=candidate_id,
            full_name=cv_data.full_name,
            email=cv_data.email,
            phone=cv_data.phone,
            applied_position=cv_data.applied_position,
            total_years_experience=cv_data.total_years_experience,
            raw_text=raw_text,
            content_hash=text_hash,
            source_job_id=job_id,
            photo_object_key=photo_object_key,
        )
        session.add(candidate)

        for skill in cv_data.skills:
            session.add(CandidateSkill(candidate_id=candidate_id, skill_name=skill))
        for exp in cv_data.experience:
            session.add(
                CandidateExperience(
                    candidate_id=candidate_id,
                    company=exp.company,
                    title=exp.title,
                    start_date=_parse_date(exp.start_date),
                    end_date=_parse_date(exp.end_date),
                    description=exp.description,
                )
            )
        for edu in cv_data.education:
            session.add(
                CandidateEducation(
                    candidate_id=candidate_id,
                    school=edu.school,
                    degree=edu.degree,
                    field=edu.field,
                    graduation_year=edu.graduation_year,
                )
            )
        for cert in cv_data.certificates:
            session.add(
                CandidateCertificate(
                    candidate_id=candidate_id,
                    name=cert.name,
                    issuer=cert.issuer,
                    issue_date=_parse_date(cert.issue_date),
                    credential_id=cert.credential_id,
                )
            )
        for proj in cv_data.projects:
            session.add(
                CandidateProject(
                    candidate_id=candidate_id,
                    name=proj.name,
                    role=proj.role,
                    tech_stack=",".join(proj.tech_stack) if proj.tech_stack else None,
                    description=proj.description,
                    start_date=_parse_date(proj.start_date),
                    end_date=_parse_date(proj.end_date),
                )
            )

        # chunking + embedding + Qdrant
        documents = build_documents_from_cv(cv_data, candidate_id, job.original_filename)

        if documents:
            texts = [d.page_content for d in documents]
            vectors = embed_texts(texts)

            chunk_ids = []
            payloads = []
            for doc, vec in zip(documents, vectors):
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                payloads.append({**doc.metadata, "chunk_text": doc.page_content})
                session.add(
                    CandidateChunk(
                        chunk_id=chunk_id,
                        candidate_id=candidate_id,
                        section_type=doc.metadata["section_type"],
                    )
                )

            qdrant = QdrantStore()
            qdrant.ensure_collection()
            qdrant.upsert_chunks(chunk_ids, vectors, payloads)

        # Update job cuối cùng
        job.candidate_id = candidate_id
        job.status = "indexed"
        session.commit()

        logger.info("Ingestion hoàn tất: job_id=%s candidate_id=%s", job_id, candidate_id)
        return candidate_id
