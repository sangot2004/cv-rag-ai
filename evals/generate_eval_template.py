"""
Tự động pre-fill evals/eval_data.json từ 1 thư mục chứa file CV PDF thật —
đỡ phải gõ tay raw_text và đáp án từ đầu. Script này CHẠY THẬT extraction
(tốn API call Gemini) để lấy draft, bạn chỉ cần REVIEW và SỬA lại chỗ sai,
không phải tự gõ từ con số 0.

LƯU Ý QUAN TRỌNG: draft sinh ra là output của chính LLM đang được eval —
không thể coi draft này là "đáp án đúng" nếu chưa tự đọc CV gốc để xác nhận.
Bỏ qua bước review sẽ khiến eval mất hết ý nghĩa (đánh giá LLM bằng chính
output của LLM luôn ra điểm tuyệt đối).
"""

from src.ingestion.parsers.pdf_parser import extract_text_from_pdf
from src.ingestion.extraction.llm_extractor import extract_cv_data
from pathlib import Path
import json
import sys

sys.path.insert(0, ".")


def main():
    if len(sys.argv) < 2:
        print("cách dùng: python evals/generate_eval_template.py thu_muc_chua_cv/")
        sys.exit(1)

    cv_dir = Path(sys.argv[1])
    pdf_files = sorted(cv_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"không tìm thấy file .pdf nào trong {cv_dir}")
        sys.exit(1)

    print(f"Tìm thấy {len(pdf_files)} file cv, đang chạy extraction để tạo draft...")

    extraction_examples = []
    for pdf_path in pdf_files:
        print(f"- Đang xử lý {pdf_path.name}...")
        raw_text = extract_text_from_pdf(pdf_path.read_bytes())
        draft = extract_cv_data(raw_text)

        extraction_examples.append(
            {
                "_source_file": pdf_path.name,
                "_review_status": "chưa review - đây là draft do llm tự sinh, cần tự đọc lại cv gốc để sửa cho đúng",
                "raw_text": raw_text,
                "expected": {
                    "full_name": draft.full_name,
                    "email": draft.email,
                    "skills": draft.skills,
                    "total_years_experience": draft.total_years_experience,
                    "num_experience_entries": len(draft.experience),
                    "num_education_entries": len(draft.education),
                },
            }
        )

    output = {
        "extraction_examples": extraction_examples,
        "agent_examples": [
            {
                "_comment": "Tự điền câu hỏi test Agent + tool đúng (filter_candidates_sql | semantic_search_cv | evaluate_candidate_against_jd)",
                "question": "VÍ DỤ: Ứng viên nào có trên 2 năm kinh nghiệm?",
                "expected_tool": "filter_candidates_sql",
            }
        ],
    }

    out_path = Path("evals/eval_data.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nĐã ghi {len(extraction_examples)} draft vào {out_path}")
    print("BƯỚC TIẾP THEO BẮT BUỘC: mở file này, đọc lại từng CV gốc, sửa phần")
    print("'expected' cho đúng, rồi xóa dòng '_review_status' — KHÔNG dùng draft")
    print("thẳng làm đáp án, vì đó chỉ là output của chính LLM đang được eval.")


if __name__ == "__main__":
    main()
