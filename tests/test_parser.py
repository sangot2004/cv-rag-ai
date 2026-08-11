from src.ingestion.parsers.pdf_parser import extract_text_from_pdf, PdfParseError

file_path = "NguyenVanA_DataEngineerintern_CV.pdf"

try:
    with open(file_path, "rb") as f:
        data = f.read()

    text = extract_text_from_pdf(data)
    print("Đọc file PDF thành công!")
    print("Số ký tự trích xuất được:", len(text))
    print("-" * 40)
    print("500 ký tự đầu tiên:")
    print(text[:500])

except PdfParseError as e:
    print(f"Lỗi khi parse file PDF: {e}")
