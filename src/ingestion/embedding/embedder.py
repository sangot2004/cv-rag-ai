import logging

from google import genai
from google.genai import types

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """lazy init - tránh crash lúc import module"""

    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Sinh embedding cho danh sách text, dùng chung 1 batch call"""
    if not texts:
        return []

    result = _get_client().models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=settings.EMBEDDING_DIM,
        ),
    )
    return [e.values for e in result.embeddings]


def embed_query(text: str) -> list[float]:
    """Dùng task_type khác (RETRIEVAL_QUERY) khi embed câu hỏi lúc search —
    Gemini tối ưu khác nhau giữa embed tài liệu để lưu và embed câu hỏi để tìm.
    """
    result = _get_client().models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=[text],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.EMBEDDING_DIM,
        ),
    )

    return result.embeddings[0].values
