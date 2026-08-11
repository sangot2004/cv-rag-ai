import fitz


class PdfParseError(Exception):
    pass


def extract_text_from_pdf(data: bytes) -> str:
    """
    Trích toàn bộ text từ pdf, giữ thứ tự trang.
    Raise pdfparseerror nếu file hỏng/k mỏ được - để tầng gọi(pipeline)
    tự quyết định retry hay chuyển DLQ, ko nuốt lỗi ở đây"""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PdfParseError(f"Không mở được PDF: {e}") from e

    try:
        pages_text = [page.get_text("text") for page in doc]
    finally:
        doc.close()

    return "\n".join(pages_text).strip()
