import logging

from google import genai
from google.genai import types

from src.config.settings import get_settings
from src.llm.key_manager import call_with_key_failover


logger = logging.getLogger(__name__)
settings = get_settings()


def _embed_call(api_key: str, texts: list[str], task_type: str) -> list[list[float]]:
    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=settings.EMBEDDING_DIM,
        ),
    )
    return [e.values for e in result.embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Sinh embedding cho danh sách text"""
    if not texts:
        return []
    return call_with_key_failover(lambda key: _embed_call(key, texts, "RETRIEVAL_DOCUMENT"))


def embed(text: str) -> list[float]:

    result = call_with_key_failover(lambda key: _embed_call(key, [text], "RETRIEVAL_QUERY"))
    return result[0]
