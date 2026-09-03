import logging
import base64

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI


from src.config.settings import get_settings
from src.ingestion.extraction.prompts import (
    CLASSIFY_CV_PROMPT,
    EXTRACT_CV_PROMPT,
    EXTRACT_JD_PROMPT,
    OCR_CV_IMAGE_PROMPT,
)
from src.llm.key_manager import call_with_key_failover
from src.schemas.cv_schema import CVClassification, CVSchema
from src.schemas.jd_schema import JDSchema

logger = logging.getLogger(__name__)
settings = get_settings()


def _classify_call(api_key: str, raw_text: str) -> CVClassification:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_CLASSIFY_MODEL, google_api_key=api_key)
    structured_llm = llm.with_structured_output(CVClassification)
    prompt = CLASSIFY_CV_PROMPT.format(text=raw_text)
    return structured_llm.invoke(prompt)


def _extract_call(api_key: str, raw_text: str) -> CVSchema:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)
    structured_llm = llm.with_structured_output(CVSchema)
    prompt = EXTRACT_CV_PROMPT.format(text=raw_text)
    return structured_llm.invoke(prompt)


def classify_is_cv(raw_text: str, max_chars: int = 3000) -> CVClassification:
    """check nd có thực sự là cv ko, trước khi tốn chi phí extraction, chỉ lấy max_chars đầu để tiết kiệm token
    đủ để phân loại"""
    text = raw_text[:max_chars]
    result = call_with_key_failover(lambda key: _classify_call(key, text))
    logger.info(
        "Classify CV: is_CV=%s confidence=%.2f reason=%s",
        result.is_cv, result.confidence, result.reason,
    )
    return result


def extract_cv_data(raw_text: str) -> CVSchema:
    """trích xuấy thành cvschema"""
    return call_with_key_failover(lambda key: _extract_call(key, raw_text))


def _ocr_call(api_key: str, images: list[bytes]) -> str:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)

    content = [{"type": "text", "text": OCR_CV_IMAGE_PROMPT}]
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append({"type": "image_url", "image_url": f"data:image/png;base64,{b64}"})

    message = HumanMessage(content=content)
    response = llm.invoke([message])
    if isinstance(response.content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response.content
        )
    return response.content


def ocr_extract_text_from_images(images: list[bytes]) -> str:
    if not images:
        return ""
    text = call_with_key_failover(lambda key: _ocr_call(key, images))
    logger.info("OCR qua Gemini vision: %d ảnh -> %d ký tự", len(images), len(text))
    return text


def _extract_jd_call(api_key: str, raw_text: str) -> JDSchema:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)
    structured_llm = llm.with_structured_output(JDSchema)
    prompt = EXTRACT_JD_PROMPT.format(text=raw_text)
    result = structured_llm.invoke(prompt)
    result.raw_text = raw_text
    return result


def extract_jd_data(raw_text: str) -> JDSchema:
    return call_with_key_failover(lambda key: _extract_jd_call(key, raw_text))
