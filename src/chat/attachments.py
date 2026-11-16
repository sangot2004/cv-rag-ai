"""Text extraction for files attached directly in the chat composer.

Mirrors the Streamlit chat_input attachment path (app.py:
extract_text_from_uploaded_file) so both front ends read PDFs/images the same
way: reuse the existing pdf_parser/OCR modules, no separate extraction logic.
"""
import io
import logging
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.auth.service import require_user
from src.chat.errors import AttachmentError
from src.config.settings import get_settings
from src.ingestion.extraction.llm_extractor import ocr_extract_text_from_images
from src.ingestion.parsers.pdf_parser import PdfParseError, extract_text_from_pdf, rasterize_pages

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_EXTRACTED_CHARS = 5000
ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".docx")
# A .docx is a zip: refuse archives that would inflate far beyond the upload cap.
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def extract_text_from_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise AttachmentError("ATTACHMENT_UNREADABLE", "File Word quá lớn sau khi giải nén.")
        document = Document(io.BytesIO(data))
    except AttachmentError:
        raise
    except Exception as e:  # corrupt zip, missing parts, bad XML
        raise AttachmentError("ATTACHMENT_UNREADABLE", "Không đọc được file Word (có thể bị hỏng).") from e

    lines = []
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            lines.append(Paragraph(child, document).text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, document).rows:
                cells = []
                for cell in row.cells:
                    if cell.text not in cells:  # merged cells repeat their text
                        cells.append(cell.text)
                lines.append(" | ".join(cells))
    return "\n".join(line for line in lines if line.strip()).strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    require_user()
    name = (filename or "").strip().lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise AttachmentError(
            "UNSUPPORTED_ATTACHMENT",
            f"Định dạng file '{filename}' chưa được hỗ trợ (chỉ PDF, Word .docx, PNG, JPG).",
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
        if name.endswith(".docx"):
            text = extract_text_from_docx(file_bytes)
        elif name.endswith(".pdf"):
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
