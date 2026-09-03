import io
import logging
import fitz

logger = logging.getLogger(__name__)


class PdfParseError(Exception):
    pass


def extract_text_from_pdf(data: bytes) -> str:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PdfParseError(f"Không mở được PDF: {e}") from e

    try:
        pages_text = [page.get_text("text") for page in doc]
    finally:
        doc.close()

    return "\n".join(pages_text).strip()


def rasterize_pages(data: bytes, max_pages: int = 3, dpi: int = 200) -> list[bytes]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PdfParseError(f"Không mở được PDF để rasterize: {e}")from e

    images = []
    try:
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        for page in doc[:max_pages]:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
    finally:
        doc.close()

    logger.info("Rasterized %d trang thành ảnh (dpi=%d)", len(images), dpi)
    return images


def extract_portrait_photo(data: bytes, max_pages_to_scan: int = 2) -> bytes | None:
    """tìm và trích ảnh chân dung từ pdf"""
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise PdfParseError(f"Không mở được PDF để tìm ảnh: {e}") from e

    best_candidate: bytes | None = None
    best_score = -1.0

    try:
        for page_num, page in enumerate(doc[:max_pages_to_scan]):
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue

                width, height = base_image.get("width", 0), base_image.get("height", 0)
                if width == 0 or height == 0:
                    continue

                aspect_ratio = height / width
                area = width * height

                # ảnh quá nhỏ or quá lớn-> cancel
                if area < 100 * 100 or area > 1200 * 1200:
                    continue
                if aspect_ratio < 0.8:
                    continue

                ratio_score = 1.0 - abs(aspect_ratio - 1.3) / 1.3
                page_score = 1.0 / (page_num + 1)
                score = ratio_score * 0.6 + page_score * 0.4

                if score > best_score:
                    best_score = score
                    best_candidate = base_image["image"]
    finally:
        doc.close()

    if best_candidate:
        logger.info("Tìm thấy ảnh chân dung khả dĩ (score=%.2f)", best_score)
    else:
        logger.info("Không tìm thấy ảnh chân dung nào khớp tiêu chí")

    return best_candidate
