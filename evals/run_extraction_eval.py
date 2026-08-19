"""
Chạy eval cho LLM Structured Extraction, dùng Dataset đã tạo qua build_dataset.py.
Kết quả xem trực tiếp trên LangSmith UI (link in ra khi chạy xong).

Cách chạy:
    python evals/run_extraction_eval.py
"""

from src.ingestion.extraction.llm_extractor import extract_cv_data
from evals.evaluators import EXTRACTION_EVALUATORS
from langsmith import evaluate
import sys

sys.path.insert(0, ".")


DATASET_NAME = "cv-extraction-eval"


def target(inputs: dict) -> dict:
    """Target function Langsmith sẽ gọi cho mỗi example trong dataset.
    inputs khớp đúng key đã lưu lúc build_dataset.py: {raw_text: "..."}"""
    cv_data = extract_cv_data(inputs["raw_text"])
    return cv_data.model_dump()


def main():
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=EXTRACTION_EVALUATORS,
        experiment_prefix="extraction-eval",
        description="Đánh giá độ chính xác structured extraction từ CV thật",
    )
    print("\n Hoàn thành. Xem chi tiết kết quả trên Langsmith dashboard.")
    print(results)


if __name__ == "__main__":
    main()
