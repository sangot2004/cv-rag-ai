import pytest
from src.auth import service as auth
from src.chat import checkpoints
from src.db.models import ChatConversation
from src.retrieval.access_scope import current_department_id


def ask(api, thread, question):
    return api.client.post(f"/api/conversations/{thread}/messages", headers=api.headers(), json={"question": question})


def test_chat_history_stable_ids_and_scope(api):
    thread = api.create()
    response = ask(api, thread, "hello")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["type"] == "answer"
    assert "hidden" not in result["message"]["content"]
    assert api.observations == [("alice", "tester", "dept-a")]
    first = api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers()).json()
    second = api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers()).json()
    assert first == second
    assert len(first["messages"]) == 2
    assert first["messages"][-1] == result["message"]
    assert first["execution_status"] == "idle"
    assert auth._token.get() is None
    assert current_department_id.get() is None


@pytest.mark.parametrize("body", [
    {"question": ""}, {"question": "   "}, {"question": "x"*20001},
    {"question": "hi", "department_id": "dept-b"}, {"question": "hi", "role": "admin"},
])
def test_bad_question(api, body):
    thread = api.create()
    assert api.client.post(f"/api/conversations/{thread}/messages", headers=api.headers(), json=body).status_code == 422


def test_confirmation_resume_snapshot_and_stale_id(api, monkeypatch):
    thread = api.create()
    first = ask(api, thread, "rank one")
    assert first.status_code == 200, first.text
    pending = first.json()["pending_confirmations"][0]
    assert pending["criteria"]["required_skills"] == ["Python"]
    with api.db() as db:
        assert db.get(ChatConversation, thread).title == "rank one"
    assert ask(api, thread, "hello").json()["error"]["code"] == "CONFIRMATION_PENDING"
    url = f"/api/conversations/{thread}/resume"
    assert api.client.post(url, headers=api.headers(), json={"confirmation_id": "stale", "confirmed": True}).json()["error"]["code"] == "STALE_CONFIRMATION"
    # New compiled graph and reader: simulate rebuilding the executor.
    monkeypatch.setattr(api.router, "_get_graph", api.build)
    monkeypatch.setattr(checkpoints, "_reader", None)
    response = api.client.post(url, headers=api.headers(), json={
        "confirmation_id": pending["confirmation_id"], "confirmed": True,
        "edited_criteria": {"top_k": 3, "min_years_experience": None, "preferred_education": None}})
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "answer"
    assert len(api.extracted) == 1
    jd, top_k, user, department = api.ranked[0]
    assert jd.required_skills == ["Python"] and jd.raw_text == "Python"
    assert jd.min_years_experience is None and jd.preferred_education is None
    assert (top_k, user, department) == (3, "alice", "dept-a")
    assert api.client.post(url, headers=api.headers(), json={
        "confirmation_id": pending["confirmation_id"], "confirmed": True}).json()["error"]["code"] == "NO_PENDING_CONFIRMATION"


def test_multiple_confirmations_and_cancel(api):
    thread = api.create()
    response = ask(api, thread, "rank two")
    assert response.status_code == 200, response.text
    pending = response.json()["pending_confirmations"]
    assert len(pending) == 2
    assert len({p["confirmation_id"] for p in pending}) == 2
    url = f"/api/conversations/{thread}/resume"
    first = api.client.post(url, headers=api.headers(), json={"confirmation_id": pending[0]["confirmation_id"], "confirmed": False})
    assert first.status_code == 200, first.text
    assert first.json()["type"] == "confirmation_required"
    remaining = first.json()["pending_confirmations"]
    assert [p["confirmation_id"] for p in remaining] == [pending[1]["confirmation_id"]]
    result = api.client.post(url, headers=api.headers(), json={"confirmation_id": pending[1]["confirmation_id"], "confirmed": True})
    assert result.status_code == 200, result.text
    assert result.json()["type"] == "answer"
    assert len(api.extracted) == 2
    assert len(api.ranked) == 1


def test_streamlit_router_contract_and_cancel(api):
    with auth.auth_scope(api.tokens["alice"]):
        from src.chat.conversation_store import create_conversation
        thread = create_conversation()
        result = api.router.ask("rank one", thread)
        assert result["type"] == "confirmation_required"
        payload = api.router.has_pending_confirmation(thread)
        assert payload["confirmation_id"] == result["payload"]["confirmation_id"]
        result = api.router.resume(thread, False, confirmation_id=payload["confirmation_id"])
        assert result["type"] == "answer"
        assert result["content"]
        assert api.router.has_pending_confirmation(thread) is None
    assert api.ranked == []
    assert len(api.extracted) == 1


@pytest.mark.parametrize("edits", [
    {"top_k": 0}, {"top_k": 11}, {"top_k": True}, {"min_years_experience": -1},
    {"required_skills": "Python"}, {"required_skills": [""]}, {"top_k": None},
    {"position_title": " "}, {"department_id": "dept-b"},
])
def test_invalid_edits_rejected_before_graph(api, edits):
    thread = api.create()
    response = api.client.post(f"/api/conversations/{thread}/resume", headers=api.headers(),
                               json={"confirmation_id": "id", "confirmed": True, "edited_criteria": edits})
    assert response.status_code == 422


@pytest.mark.parametrize("error,status,code", [
    (RuntimeError("SECRET"), 500, "INTERNAL_ERROR"),
    (TimeoutError("SECRET"), 504, "DEPENDENCY_TIMEOUT"),
    (RuntimeError("429 RESOURCE_EXHAUSTED SECRET"), 503, "DEPENDENCY_UNAVAILABLE"),
])
def test_failed_turn_sanitized_and_no_automatic_retry(api, monkeypatch, error, status, code):
    from types import SimpleNamespace
    monkeypatch.setattr(api.router, "get_key_manager", lambda: SimpleNamespace(mark_exhausted=lambda: None))
    thread = api.create()
    api.failure.append(error)
    response = ask(api, thread, "fail")
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert "SECRET" not in response.text
    state = api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers()).json()
    assert state["execution_status"] == "failed"
    assert len(state["messages"]) == 1
    assert ask(api, thread, "hello").json()["error"]["code"] == "EXECUTION_INCOMPLETE"
