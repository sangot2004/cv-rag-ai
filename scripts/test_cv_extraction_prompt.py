"""Pull a LangSmith CV prompt and try it with a sample, text, or PDF CV."""

import argparse
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

from src.llm.prompt_store import get_prompt_commit

PROMPT_IDENTIFIER = f"cv-rag-extract-cv:{get_prompt_commit('cv-rag-extract-cv')}"
SAMPLE_CV = """Nguyễn An Bình
Email: an.binh@example.com
Vị trí ứng tuyển: Backend Developer
Kỹ năng: Python, FastAPI, PostgreSQL
Kinh nghiệm: Backend Developer tại Công ty ABC, 2022-01 đến 2024-01.
Xây dựng API bằng FastAPI và PostgreSQL.
Học vấn: Cử nhân Công nghệ thông tin, Đại học XYZ, tốt nghiệp 2021.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cv-file", type=Path, help="Đường dẫn tới CV dạng .pdf hoặc .txt; mặc định dùng CV giả lập.")
    parser.add_argument("--prompt", default=PROMPT_IDENTIFIER, help="Tên prompt kèm commit hoặc tag.")
    parser.add_argument("--pull-only", action="store_true", help="Chỉ kéo và điền prompt, không gọi Gemini.")
    args = parser.parse_args()

    load_dotenv()
    if args.cv_file is None:
        raw_text = SAMPLE_CV
    elif args.cv_file.suffix.lower() == ".pdf":
        from src.ingestion.parsers.pdf_parser import extract_text_from_pdf

        raw_text = extract_text_from_pdf(args.cv_file.read_bytes())
    elif args.cv_file.suffix.lower() == ".txt":
        raw_text = args.cv_file.read_text(encoding="utf-8")
    else:
        parser.error("--cv-file chỉ hỗ trợ file .pdf hoặc .txt.")
    if not raw_text.strip():
        parser.error("CV đầu vào đang rỗng.")

    template = Client().pull_prompt(args.prompt)
    if set(template.input_variables) != {"text"}:
        raise ValueError(f"Prompt cần đúng biến {{text}}, nhận được: {template.input_variables}")
    prompt_value = template.format_prompt(text=raw_text)
    print(f"Đã kéo prompt: {args.prompt}")

    if args.pull_only:
        print(f"Đã điền CV vào prompt ({len(prompt_value.to_string())} ký tự).")
        return

    from langchain_google_genai import ChatGoogleGenerativeAI

    from src.config.settings import get_settings
    from src.llm.key_manager import call_with_key_failover
    from src.schemas.cv_schema import CVSchema

    model = get_settings().GEMINI_LLM_MODEL

    def extract(api_key: str) -> CVSchema:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key)
        return llm.with_structured_output(CVSchema).invoke(prompt_value)

    result = call_with_key_failover(extract)
    print(f"Kết quả từ {model}:")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
