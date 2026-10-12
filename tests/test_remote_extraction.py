from src.ingestion.extraction import llm_extractor
from src.ops import optimization
from src.schemas.cv_schema import CVSchema


def test_extraction_uses_same_pinned_prompt_for_cache_and_model(monkeypatch):
    observed = {}

    def fake_format(name, *, commit, text):
        assert name == "cv-rag-extract-cv"
        assert commit == "deadbeef"
        return f"Remote instructions: {text}"

    def fake_cache(text, model, prompt, schema, compute, enabled):
        observed["cache_prompt"] = prompt
        return compute()

    def fake_extract(key, raw_text, model, *, prompt_text):
        observed["model_prompt"] = prompt_text
        return CVSchema(full_name="Test Candidate")

    monkeypatch.setattr(llm_extractor, "format_prompt", fake_format)
    monkeypatch.setattr(llm_extractor, "_extract_call", fake_extract)
    monkeypatch.setattr(llm_extractor, "call_with_key_failover", lambda fn: fn("test-key"))
    monkeypatch.setattr(optimization, "active_config", lambda: {
        "extraction_model": "test-model",
        "extraction_prompt_version": "deadbeef",
        "cache_enabled": True,
    })
    monkeypatch.setattr(optimization, "cached_extract", fake_cache)

    result = llm_extractor.extract_cv_data("CV text")

    assert result.full_name == "Test Candidate"
    assert observed == {
        "cache_prompt": "Remote instructions: CV text",
        "model_prompt": "Remote instructions: CV text",
    }


def test_model_receives_supplied_prompt_without_pulling_again(monkeypatch):
    calls = []

    class FakeLLM:
        def with_structured_output(self, schema):
            assert schema is CVSchema
            return self

        def invoke(self, prompt):
            calls.append(prompt)
            return CVSchema(full_name="Test Candidate")

    def unexpected_pull(*args, **kwargs):
        raise AssertionError("unexpected pull")

    monkeypatch.setattr(llm_extractor, "ChatGoogleGenerativeAI", lambda **kwargs: FakeLLM())
    monkeypatch.setattr(llm_extractor, "format_prompt", unexpected_pull)

    result = llm_extractor._extract_call("test-key", "CV text", "test-model", prompt_text="Approved prompt")

    assert result.full_name == "Test Candidate"
    assert calls == ["Approved prompt"]
