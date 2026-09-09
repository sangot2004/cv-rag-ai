"""
Test A2 — src/ingestion/parsers/pdf_parser.py
Test 2 hàm mới ĐỘC LẬP, không cần Gemini/DB/Redis:
  - rasterize_pages()       : render trang PDF -> ảnh PNG (dùng cho OCR fallback)
  - extract_portrait_photo(): heuristic tách ảnh chân dung khỏi PDF

Cách chạy:
    PYTHONPATH=. python3 test_pdf_parser_a2.py <duong_dan_file_cv.pdf>

Nếu không truyền path, script sẽ hỏi nhập tay.
Output ảnh được lưu vào /tmp/ để bạn tự mở xem bằng mắt.
"""

from src.ingestion.parsers.pdf_parser import (
    PdfParseError,
    extract_portrait_photo,
    rasterize_pages,
)
import sys

sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def test_rasterize_pages(data: bytes):
    step("Test 1: rasterize_pages()")
    try:
        images = rasterize_pages(data, max_pages=2)
    except PdfParseError as e:
        print(f"!! Lỗi mở/render PDF: {e}")
        return

    print(f"Render được {len(images)} ảnh")
    if not images:
        print("!! Không có ảnh nào được render — kiểm tra lại file PDF")
        return

    for i, img_bytes in enumerate(images):
        out_path = f"/tmp/test_page{i + 1}.png"
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        print(f"  - Trang {i + 1}: {len(img_bytes):,} bytes -> đã lưu {out_path}")

    print(f"\n-> Mở {len(images)} file /tmp/test_page*.png xem có đúng là trang CV không")


def test_extract_portrait_photo(data: bytes):
    step("Test 2: extract_portrait_photo()")
    try:
        photo_bytes = extract_portrait_photo(data, max_pages_to_scan=2)
    except PdfParseError as e:
        print(f"!! Lỗi mở PDF để tìm ảnh: {e}")
        return

    if photo_bytes is None:
        print("Không tìm thấy ảnh chân dung nào khớp tiêu chí.")
        print("(Bình thường nếu CV này không có ảnh, hoặc heuristic bỏ sót — best-effort)")
        return

    out_path = "/tmp/test_portrait.jpg"
    with open(out_path, "wb") as f:
        f.write(photo_bytes)
    print(f"Tìm thấy ảnh khả dĩ: {len(photo_bytes):,} bytes -> đã lưu {out_path}")
    print(f"\n-> Mở {out_path} xem có đúng là ảnh chân dung không, hay bị nhầm với logo/icon")


def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = input("Nhập đường dẫn tới file CV PDF: ").strip()

    if not pdf_path:
        print("!! Chưa nhập đường dẫn file. Dừng.")
        sys.exit(1)

    try:
        data = load_pdf_bytes(pdf_path)
    except FileNotFoundError:
        print(f"!! Không tìm thấy file: {pdf_path}")
        sys.exit(1)

    print(f"Đã đọc file: {pdf_path} ({len(data):,} bytes)")

    test_rasterize_pages(data)
    test_extract_portrait_photo(data)

    step("HOÀN THÀNH — test A2 xong")
    print("Lưu ý: extract_portrait_photo là heuristic best-effort — nên test")
    print("với nhiều CV thật khác nhau (có/không có ảnh) để tự đánh giá tỷ lệ đúng/sai.")


if __name__ == "__main__":
    main()
