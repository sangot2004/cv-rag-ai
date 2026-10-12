"""Manually check that a second CV extraction uses the Redis cache.

Run from the project root with an optional local text CV:
    PYTHONPATH=. python scripts/test_ops_cache_manual.py --cv-file test_cv.txt

This script makes one real Gemini call and requires LangSmith and Redis.
"""

import argparse
import time
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


SAMPLE_CV = """Nguyễn An Bình
Email: an.binh@example.com
Vị trí ứng tuyển: Backend Developer
Kỹ năng: Python, FastAPI, PostgreSQL
Kinh nghiệm: Backend Developer tại Công ty ABC, 2022-01 đến 2024-01.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cv-file",
        type=Path,
        help="Đường dẫn tới CV .txt; mặc định dùng CV giả lập.",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    raw_text = args.cv_file.read_text(encoding="utf-8") if args.cv_file else SAMPLE_CV
    if not raw_text.strip():
        parser.error("CV đầu vào đang rỗng.")

    from src.config.settings import get_settings
    from src.ingestion.extraction.llm_extractor import _extract_call
    from src.llm.key_manager import call_with_key_failover
    from src.llm.prompt_store import format_prompt
    from src.ops.optimization import cached_extract
    from src.schemas.cv_schema import CVSchema

    model = get_settings().GEMINI_LLM_MODEL
    cache_prompt = format_prompt("cv-rag-extract-cv", text=raw_text) + f"\nCache test ID: {uuid4()}"
    model_calls = 0

    def compute():
        nonlocal model_calls
        model_calls += 1
        print("Đang gọi model...")
        return call_with_key_failover(
            lambda key: _extract_call(key, raw_text, model, prompt_text=cache_prompt)
        )

    def run_once():
        started = time.perf_counter()
        result = cached_extract(raw_text, model, cache_prompt, CVSchema, compute, True)
        print(f"Thời gian: {time.perf_counter() - started:.2f}s")
        return result

    print("Lần 1:")
    first = run_once()
    print("\nLần 2:")
    second = run_once()
    print("\nSố lần gọi compute:", model_calls)
    print("Hai kết quả giống nhau:", first.model_dump() == second.model_dump())

    assert model_calls == 1, "Cache chưa hoạt động: compute được gọi lại."
    assert first.model_dump() == second.model_dump(), "Kết quả cache khác."
    print("PASS: lần 2 lấy từ cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
