import hashlib
import logging
import re
from dataclasses import dataclass

import fitz

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_FILENAME_RE = re.compile(settings.CV_FILENAME_PATTERN, re.IGNORECASE)


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str | None = None  # why rejected, khớp với error message trong ingestion_jobs table


def validate_filename(filename: str) -> ValidationResult:
    """ 3.1 đúng định dạng tên file bắt buộc"""
    if not _FILENAME_RE.match(filename):
        return ValidationResult(False, f"invalid_filename_format: {filename}")
    return ValidationResult(True)


def validate_extension(filename: str) -> ValidationResult:
    """ 2.1 đúng định dạng file type bắt buộc - pdf"""
    if not filename.lower().endswith(".pdf"):
        return ValidationResult(False, "not_pdf_extension")
    return ValidationResult(True)


def validate_size(data: bytes) -> ValidationResult:
    """2.3 + 3.2 - dung lượng size trong khoảng"""
    size = len(data)
    if size < settings.CV_MIN_FILE_SIZE_BYTES:
        return ValidationResult(False, f"file_too_small: {size} bytes")
    if size > settings.CV_MAX_FILE_SIZE_BYTES:
        return ValidationResult(False, f"file_too_large: {size} bytes")
    return ValidationResult(True)


def validate_magic_bytes(data: bytes) -> ValidationResult:
    header_window = data[:1024]
    if b"%PDF-" not in header_window:
        return ValidationResult(False, "invalid_magic_bytes_not_pdf")
    return ValidationResult(True)


def validate_pdf_integrity(data: bytes) -> ValidationResult:
    """3.4 + 3.5 + 3.6"""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        return ValidationResult(False, f"corrupted_pdf: {str(e)}")

    if doc.is_encrypted:
        doc.close()
        return ValidationResult(False, "pdf_is_encrypted")

    page_count = len(doc)
    doc.close()
    if page_count == 0:
        return ValidationResult(False, "pdf_has_no_pages")
    if page_count > settings.CV_MAX_PAGES:
        return ValidationResult(False, f"pdf_too_many_pages: {page_count}")

    return ValidationResult(True)


def compute_content_hash(data: bytes) -> str:
    """4.3 - check trùng file"""
    return hashlib.sha256(data).hexdigest()


def run_all_validations(filename: str, data: bytes) -> ValidationResult:
    """Run từng check, dừng check đầu tiên bị fail"""
    checks = [
        lambda: validate_extension(filename),
        lambda: validate_filename(filename),
        lambda: validate_size(data),
        lambda: validate_magic_bytes(data),
        lambda: validate_pdf_integrity(data),
    ]
    for check in checks:
        result = check()
        if not result.is_valid:
            return result
    return ValidationResult(True)
