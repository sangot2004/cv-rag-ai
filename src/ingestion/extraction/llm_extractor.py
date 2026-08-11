import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import get_settings
from src.ingestion.extraction.prompts import CLASSIFY_CV_PROMPT, EXTRACT_CV_PROMPT
from src.schemas.cv_schema import CVClassification, CVSchema

logger = logging.getLogger(__name__)
settings = get_settings()

# dùng model flash-lite
_classify_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_CLASSIFY_MODEL, google_api_key=settings.GOOGLE_API_KEY
)
# Model mạnh hơn (Flash) cho bước trích xuất đầy đủ (A6) — cần suy luận tốt hơn
_extract_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_LLM_MODEL, google_api_key=settings.GOOGLE_API_KEY
)


def classify_is_cv(raw_text: str, max_chars: int = 3000) -> CVClassification:
    """check nd có thực sự là cv ko, trước khi tốn chi phí extraction, chỉ lấy max_chars đầu để tiết kiệm token
    đủ để phân loại"""
    structured_llm = _classify_llm.with_structured_output(CVClassification)
    prompt = CLASSIFY_CV_PROMPT.format(text=raw_text[:max_chars])
    result = structured_llm.invoke(prompt)
    logger.info(
        "Classify CV: is_cv=%s confidence=%.2f reason=%s",
        result.is_cv, result.confidence, result.reason,
    )
    return result


def extract_cv_data(raw_text: str) -> CVSchema:
    """trích xuấy thành cvschema"""
    structured_llm = _extract_llm.with_structured_output(CVSchema)
    prompt = EXTRACT_CV_PROMPT.format(text=raw_text)
    return structured_llm.invoke(prompt)
