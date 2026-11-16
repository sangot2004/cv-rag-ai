import fitz

from src.chat import attachments


def pdf_bytes(text="Candidate CV Python"):
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), text)
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
