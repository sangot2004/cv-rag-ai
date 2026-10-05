import logging

from google import genai
from google.genai import types

from src.ops.telemetry import monitored
from src.config.settings import get_settings
from src.llm.key_manager import call_with_key_failover


logger = logging.getLogger(__name__)
settings = get_settings()


def _embed_call(api_key: str, texts: list[str], task_type: str) -> list[list[float]]:
    client = genai.Client(api_key=api_key)

    import time
    from src.ops.telemetry import record_usage

    started = time.perf_counter()
    try:
        result = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=settings.EMBEDDING_DIM,
            ),
        )
    except Exception as exc:
        record_usage(settings.GEMINI_EMBEDDING_MODEL, (time.perf_counter() - started) * 1000,
                     status="error", error_type=type(exc).__name__)
        raise
    counts = [
        getattr(getattr(embedding, "statistics", None), "token_count", None)
        for embedding in result.embeddings
    ]
    count = sum(counts) if counts and all(value is not None for value in counts) else None
    record_usage(settings.GEMINI_EMBEDDING_MODEL, (time.perf_counter() - started) * 1000,
                 {"input_tokens": count, "output_tokens": 0})

    return [e.values for e in result.embeddings]


@monitored('embedding_documents', ref=None)
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Sinh embedding cho danh sách text"""
    if not texts:
        return []
    return call_with_key_failover(lambda key: _embed_call(key, texts, "RETRIEVAL_DOCUMENT"))


@monitored('embedding_query', ref=None)
def embed_query(text: str) -> list[float]:

    result = call_with_key_failover(lambda key: _embed_call(key, [text], "RETRIEVAL_QUERY"))
    return result[0]
