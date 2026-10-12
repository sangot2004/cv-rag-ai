from types import SimpleNamespace

from scripts import check_langsmith_prompts as checker
from src.ops import optimization


def test_checker_includes_active_extraction_commit(monkeypatch, capsys):
    monkeypatch.setattr(checker, "DEFAULT_PROMPT_COMMITS", {
        "cv-rag-extract-cv": "55c22bda",
        "cv-rag-agent-system": "73398ad0",
    })
    monkeypatch.setattr(optimization, "active_config", lambda: {
        "extraction_prompt_version": "deadbeef"
    })
    pulled = []
    formatted = []

    class FakeClient:
        def get_prompt(self, name):
            return SimpleNamespace(is_public=False)

        def pull_prompt_commit(self, identifier, *, skip_cache):
            assert skip_cache is True
            pulled.append(identifier)
            return SimpleNamespace(commit_hash=identifier.split(":")[1], manifest={"ok": True})

    def fake_get_prompt_text(name, *, commit):
        formatted.append((name, commit))
        return "valid template"

    monkeypatch.setattr(checker, "Client", FakeClient)
    monkeypatch.setattr(checker, "get_prompt_text", fake_get_prompt_text)

    assert checker.main([]) == 0
    assert pulled == [
        "cv-rag-extract-cv:55c22bda",
        "cv-rag-agent-system:73398ad0",
        "cv-rag-extract-cv:deadbeef",
    ]
    assert ("cv-rag-extract-cv", "deadbeef") in formatted
    assert "3 phiên bản prompt; lỗi: 0" in capsys.readouterr().out


def test_checker_fails_if_active_commit_is_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(checker, "DEFAULT_PROMPT_COMMITS", {"cv-rag-extract-cv": "55c22bda"})
    monkeypatch.setattr(optimization, "active_config", lambda: {
        "extraction_prompt_version": "deadbeef"
    })

    class FakeClient:
        def get_prompt(self, name):
            return SimpleNamespace(is_public=False)

        def pull_prompt_commit(self, identifier, *, skip_cache):
            if identifier.endswith(":deadbeef"):
                raise FileNotFoundError("commit unavailable")
            return SimpleNamespace(commit_hash="55c22bda", manifest={"ok": True})

    monkeypatch.setattr(checker, "Client", FakeClient)
    monkeypatch.setattr(checker, "get_prompt_text", lambda name, *, commit: "valid template")

    assert checker.main([]) == 1
    assert "Không kiểm tra được cv-rag-extract-cv:deadbeef" in capsys.readouterr().out


def test_checker_reports_active_config_error(monkeypatch, capsys):
    def fail_config():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(optimization, "active_config", fail_config)
    assert checker.main(["--dry-run"]) == 1
    assert "database unavailable" in capsys.readouterr().out
