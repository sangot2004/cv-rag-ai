"""Text extraction for files attached directly in the chat composer.

Mirrors the Streamlit chat_input attachment path (app.py:
extract_text_from_uploaded_file) so both front ends read PDFs/images the same
way: reuse the existing pdf_parser/OCR modules, no separate extraction logic.
"""
import logging

from src.auth.service import require_user
from src.chat.errors import AttachmentError
from src.config.settings import get_settings
from src.ingestion.extraction.llm_extractor import ocr_extract_text_from_images
from src.ingestion.parsers.pdf_parser import PdfParseError, extract_text_from_pdf, rasterize_pages

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_EXTRACTED_CHARS = 5000
ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")


def extract_text(file_bytes: bytes, filename: str) -> str:
    require_user()
    name = (filename or "").strip().lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise AttachmentError(
            "UNSUPPORTED_ATTACHMENT",
            f"Định dạng file '{filename}' chưa được hỗ trợ (chỉ PDF, PNG, JPG).",
        )
    if not file_bytes:
        raise AttachmentError("EMPTY_ATTACHMENT", f"File '{filename}' rỗng.")
    if len(file_bytes) > MAX_ATTACHMENT_BYTES:
        raise AttachmentError(
            "ATTACHMENT_TOO_LARGE",
            "File vượt quá dung lượng cho phép (tối đa 15MB).",
            413,
        )

    try:
        if name.endswith(".pdf"):
            text = extract_text_from_pdf(file_bytes)
            if len(text) < settings.CV_MIN_TEXT_LENGTH:
                images = rasterize_pages(file_bytes)
                text = ocr_extract_text_from_images(images)
        else:
            text = ocr_extract_text_from_images([file_bytes])
    except PdfParseError as e:
        raise AttachmentError("ATTACHMENT_UNREADABLE", str(e)) from e

    logger.info("Attachment '%s' extracted: %d ký tự", filename, len(text))
    return text[:MAX_EXTRACTED_CHARS]
