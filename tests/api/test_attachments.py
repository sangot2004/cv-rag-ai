import fitz

from src.chat import attachments


def pdf_bytes(text="Candidate CV Python"):
    # Repeat on several lines so the extracted text clears CV_MIN_TEXT_LENGTH
    # and the OCR/Gemini fallback (needs a real GOOGLE_API_KEY) never triggers.
    with fitz.open() as doc:
        page = doc.new_page()
        for line in range(6):
            page.insert_text((40, 40 + line * 20), text)
        return doc.tobytes()


def test_extract_pdf_text_layer(api):
    response = api.client.post(
        "/api/attachments/extract",
        headers=api.headers("alice"),
        files={"file": ("jd.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "jd.pdf"
    assert "Candidate CV Python" in body["text"]


def test_extract_requires_auth(api):
    response = api.client.post(
        "/api/attachments/extract",
        files={"file": ("jd.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 401


def test_extract_rejects_unsupported_format(api):
    response = api.client.post(
        "/api/attachments/extract",
        headers=api.headers("alice"),
        files={"file": ("resume.docx", b"not a real docx", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_ATTACHMENT"


def test_extract_rejects_oversized_file(api, monkeypatch):
    monkeypatch.setattr(attachments, "MAX_ATTACHMENT_BYTES", 10)
    response = api.client.post(
        "/api/attachments/extract",
        headers=api.headers("alice"),
        files={"file": ("jd.pdf", pdf_bytes(), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "ATTACHMENT_TOO_LARGE"


def test_extract_rejects_empty_file(api):
    response = api.client.post(
        "/api/attachments/extract",
        headers=api.headers("alice"),
        files={"file": ("jd.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 422


def test_split_attachments_hides_extracted_text():
    from src.chat.message_adapter import split_attachments
    question = ("Đánh giá JD này\n\n--- Nội dung file 'jd.pdf' ---\nNhiều dòng\ntext\n\n"
                "--- Nội dung file 'b.png' ---\nthêm")
    assert split_attachments(question) == ("Đánh giá JD này", ["jd.pdf", "b.png"])
    assert split_attachments("Câu hỏi thường") == ("Câu hỏi thường", [])
