"""
Test OCR fallback (Bước A3 — bổ sung vòng 2, mục 9.1):
  rasterize_pages() -> ocr_extract_text_from_images()

Cách chạy:
    # Test với CV scan thật (khuyến nghị — kết quả đáng tin cậy hơn):
    python3 test_ocr_fallback.py --pdf duong_dan_toi_cv_scan_that.pdf

    # Không có CV scan thật sẵn? Tự tạo 1 bản giả lập để test nhanh luồng
    # code (KHÔNG thay thế cho việc test với ảnh chụp/scan thật — chữ máy
    # tính vẽ ra "sạch" hơn nhiều so với ảnh chụp giấy thật ngoài đời):
    python3 test_ocr_fallback.py --generate-fake

So sánh kỹ text OCR ra với ảnh gốc — đặc biệt để ý:
  - Số điện thoại, email (dễ lẫn 0/O, 1/l/I, 5/S, 8/B)
  - Tên riêng có dấu tiếng Việt
  - Bảng/cột kép (OCR đôi khi đọc sai thứ tự khi có nhiều cột)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def generate_fake_scanned_cv(output_path: str) -> None:
    """Tạo 1 PDF giả lập kiểu 'CV scan' — vẽ text lên ảnh trắng rồi lưu
    thành PDF chỉ chứa ảnh (không có text layer thật), giống cấu trúc 1
    CV bị scan/chụp ảnh. Dùng Pillow trực tiếp (Image.save format PDF),
    không cần cài thêm img2pdf.

    LƯU Ý: đây chỉ là cách kiểm tra nhanh luồng code có chạy được không.
    Text vẽ ra bằng font hệ thống rất "sạch" và thẳng hàng — không phản
    ánh đúng độ khó thật của ảnh chụp CV giấy ngoài đời (nghiêng, mờ,
    bóng, nhòe). Trước khi tin tưởng OCR, vẫn cần test với ảnh chụp thật.
    """
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1240, 1754  # xấp xỉ khổ A4 ở 150 DPI
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        # Fallback nếu không tìm thấy font TrueType trong môi trường —
        # dùng font mặc định của Pillow (xấu hơn nhưng vẫn chạy được).
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    lines = [
        ("NGUYỄN VĂN TEST", font_title),
        ("", font_body),
        ("Data Engineer", font_body),
        ("Điện thoại: 0912345678", font_body),
        ("Email: nguyenvantest@gmail.com", font_body),
        ("Địa chỉ: Hà Nội, Việt Nam", font_body),
        ("", font_body),
        ("HỌC VẤN", font_title),
        ("Đại học Bách Khoa Hà Nội — Công nghệ thông tin (2020-2024)", font_body),
        ("", font_body),
        ("KỸ NĂNG", font_title),
        ("Python, SQL, Airflow, Docker, Spark", font_body),
        ("", font_body),
        ("KINH NGHIỆM", font_title),
        ("Data Engineer Intern tại ABC Corp (06/2023 - 12/2023)", font_body),
        ("- Xây dựng pipeline ETL xử lý 1 triệu bản ghi/ngày", font_body),
        ("- Tối ưu truy vấn SQL giảm 40% thời gian chạy job", font_body),
    ]

    y = 80
    for text, font in lines:
        draw.text((80, y), text, fill="black", font=font)
        y += 55

    img.save(output_path, "PDF", resolution=150.0)
    print(f"Đã tạo CV giả lập tại: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Test OCR fallback qua Gemini vision")
    parser.add_argument("--pdf", type=str, help="Đường dẫn tới CV scan/ảnh thật (.pdf)")
    parser.add_argument(
        "--generate-fake",
        action="store_true",
        help="Tự tạo 1 CV giả lập để test nhanh (không thay thế test với ảnh chụp thật)",
    )
    parser.add_argument("--max-pages", type=int, default=3, help="Số trang tối đa render (mặc định 3)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI khi render trang PDF (mặc định 200)")
    args = parser.parse_args()

    if not args.pdf and not args.generate_fake:
        print("Cần chỉ định --pdf <đường dẫn> hoặc --generate-fake. Xem --help để biết cách dùng.")
        sys.exit(1)

    if args.generate_fake:
        step("Bước 0: Tạo CV giả lập (không có sẵn CV scan thật)")
        fake_path = "fake_scanned_cv.pdf"
        generate_fake_scanned_cv(fake_path)
        pdf_path = fake_path
    else:
        pdf_path = args.pdf

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"!! Không tìm thấy file: {pdf_path}")
        sys.exit(1)

    # ---- Bước 1: Rasterize PDF thành ảnh ----
    step("Bước 1: Rasterize PDF thành ảnh (rasterize_pages)")
    from src.ingestion.parsers.pdf_parser import rasterize_pages

    data = pdf_file.read_bytes()
    print(f"Đọc file: {pdf_path} ({len(data):,} bytes)")

    images = rasterize_pages(data, max_pages=args.max_pages, dpi=args.dpi)
    print(f"Đã render {len(images)} trang thành ảnh (dpi={args.dpi})")

    if not images:
        print("!! Không render được trang nào — kiểm tra lại file PDF có hợp lệ không.")
        sys.exit(1)

    # Lưu ảnh ra đĩa để bạn tự mở xem, đối chiếu bằng mắt với text OCR ra
    out_dir = Path("ocr_test_output")
    out_dir.mkdir(exist_ok=True)
    for i, img_bytes in enumerate(images):
        img_path = out_dir / f"page_{i + 1}.png"
        img_path.write_bytes(img_bytes)
    print(f"Đã lưu {len(images)} ảnh trang vào: {out_dir}/ (để bạn đối chiếu bằng mắt)")

    input("\n-> Enter để gửi ảnh cho Gemini OCR...")

    # ---- Bước 2: OCR qua Gemini vision ----
    step("Bước 2: OCR qua Gemini (ocr_extract_text_from_images)")
    from src.ingestion.extraction.llm_extractor import ocr_extract_text_from_images

    text = ocr_extract_text_from_images(images)
    print(f"OCR ra {len(text)} ký tự\n")
    print("-" * 60)
    print(text)
    print("-" * 60)

    # ---- Bước 3: Check nhanh các điểm dễ sai (heuristic, không thay thế đọc bằng mắt) ----
    step("Bước 3: Check nhanh — pattern số điện thoại / email")
    import re

    phones = re.findall(r"(?:\+84|0)\d{9,10}", text)
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)

    print(f"Số điện thoại tìm thấy: {phones or '(không thấy)'}")
    print(f"Email tìm thấy: {emails or '(không thấy)'}")
    print(
        "\nLưu ý: check này chỉ dò theo regex cơ bản, KHÔNG xác nhận số/email"
        " đó có ĐÚNG với ảnh gốc hay không — vẫn cần bạn tự đối chiếu bằng mắt"
        " với ảnh trong thư mục ocr_test_output/."
    )

    # ---- Bước 4 (tùy chọn): thử extract full luôn từ text OCR ra ----
    step("Bước 4: Chạy tiếp extract_cv_data() từ text OCR (tùy chọn)")
    run_full = input("Chạy luôn extract_cv_data() với text OCR ra? (y/N): ").strip().lower()
    if run_full == "y":
        from src.ingestion.extraction.llm_extractor import extract_cv_data

        cv_data = extract_cv_data(text)
        print("\nKết quả extract_cv_data():")
        print(cv_data.model_dump_json(indent=2, exclude_none=True))

    step("HOÀN THÀNH — test OCR fallback")
    print(
        f"\nĐối chiếu thủ công: mở {out_dir}/page_1.png cạnh text OCR ở trên,"
        " so từng dòng — đặc biệt số điện thoại/email/tên riêng có dấu."
    )


if __name__ == "__main__":
    main()
