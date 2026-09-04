"""
Test Luồng A + B từng bước, dùng 1 file CV PDF thật làm input.
Không đụng tới Gmail/Celery — chỉ test đúng phần pipeline xử lý.

Cách chạy:
    python test_pipeline.py duong_dan_toi_file_cv.pdf

Yêu cầu trước khi chạy:
    - .env đã có GOOGLE_API_KEY
    - MySQL đã có bảng (alembic upgrade head)
    - Qdrant đã tạo collection (python scripts/init_qdrant_collection.py)
    - MinIO đang chạy (không bắt buộc cho test này — script tự upload file
      test lên MinIO trước, y hệt bước A0, để có object_key hợp lệ cho A3)
"""

from src.storage.minio_client import MinioStorage
from src.ingestion.pipeline import run_ingestion_pipeline
from src.ingestion.parsers.pdf_parser import extract_text_from_pdf
from src.ingestion.extraction.llm_extractor import classify_is_cv, extract_cv_data
from src.ingestion.embedding.embedder import embed_texts
from src.ingestion.chunking.document_builder import build_documents_from_cv
from src.db.session import SessionLocal
from src.db.models import IngestionJob
import sys
import uuid

sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python test_pipeline.py duong_dan_toi_file_cv.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # ---- Bước 1: Parse ----
    step("BƯỚC 1: Parse PDF")
    raw_text = extract_text_from_pdf(file_bytes)
    print(f"Số ký tự: {len(raw_text)}")
    print(f"200 ký tự đầu:\n{raw_text[:200]}")
    input("\n-> Đọc thử, đúng là text CV thì Enter để tiếp tục...")

    # ---- Bước 2: Classify ----
    step("BƯỚC 2: Classify có phải CV không")
    classification = classify_is_cv(raw_text)
    print(f"is_cv={classification.is_cv}  confidence={classification.confidence:.2f}")
    print(f"reason: {classification.reason}")
    if not classification.is_cv:
        print("!! Model kết luận đây KHÔNG phải CV — dừng test tại đây.")
        sys.exit(1)
    input("\n-> Đúng là CV thì Enter để tiếp tục...")

    # ---- Bước 3: Extract ----
    step("BƯỚC 3: LLM Structured Extraction")
    cv_data = extract_cv_data(raw_text)
    print(cv_data.model_dump_json(indent=2, exclude={"raw_text"}))
    input("\n-> Kiểm tra thông tin có đúng CV thật không, Enter để tiếp tục...")

    # ---- Bước 4: Chunking ----
    step("BƯỚC 4: Chunking theo section")
    documents = build_documents_from_cv(cv_data, candidate_id="test-preview", source_file=pdf_path)
    print(f"Số chunk: {len(documents)}")
    for d in documents:
        print(f"  [{d.metadata['section_type']}] {d.page_content[:80]}...")
    input("\n-> Enter để tiếp tục sang bước embedding...")

    # ---- Bước 5: Embedding ----
    step("BƯỚC 5: Sinh embedding")
    texts = [d.page_content for d in documents]
    vectors = embed_texts(texts)
    print(f"Số vector: {len(vectors)}, chiều mỗi vector: {len(vectors[0])}")
    assert len(vectors[0]) == 768, f"CẢNH BÁO: vector {len(vectors[0])} chiều, không phải 768!"
    input("\n-> Đúng 768 chiều thì Enter để chạy full pipeline (ghi thật vào DB)...")

    # ---- Bước 6: Full pipeline thật (ghi MySQL + Qdrant) ----
    step("BƯỚC 6: Chạy full pipeline — TẠO JOB GIẢ, GHI THẬT VÀO DB")

    job_id = str(uuid.uuid4())
    storage = MinioStorage()
    object_key = storage.build_object_key(job_id, "test_pipeline_cv.pdf")
    storage.upload_bytes(object_key, file_bytes)
    print(f"Đã upload file test lên MinIO: {object_key}")

    with SessionLocal() as session:
        job = IngestionJob(
            job_id=job_id,
            source_type="manual_test",
            minio_bucket=storage.bucket,
            minio_object_key=object_key,
            original_filename="test_pipeline_cv.pdf",
            file_type="pdf",
            status="pending",
        )
        session.add(job)
        session.commit()
    print(f"Đã tạo ingestion_jobs test: job_id={job_id}")

    candidate_id = run_ingestion_pipeline(job_id)

    step("KẾT QUẢ")
    print(f"candidate_id = {candidate_id}")
    print("\nVerify bằng lệnh:")
    print(f"  docker exec -it cvrag-mysql mysql -uadmin -p123456 cv_rag_db \\")
    print(f'    -e "SELECT * FROM candidates WHERE candidate_id=\'{candidate_id}\'\\G"')
    print(f"  docker exec -it cvrag-mysql mysql -uadmin -p123456 cv_rag_db \\")
    print(f'    -e "SELECT * FROM candidate_experience WHERE candidate_id=\'{candidate_id}\'\\G"')
    print("  Mở http://localhost:6333/dashboard -> collection cv_chunks -> xem point mới")


if __name__ == "__main__":
    main()
