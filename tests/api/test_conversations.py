from uuid import uuid4
import sqlite3

from src.chat import checkpoints
from src.db.models import ChatConversation, ChatFeedback


def test_create_list_ownership_and_delete(api):
    client, headers = api.client, api.headers()
    created = client.post("/api/conversations", headers=headers, json={})
    assert created.status_code == 201
    row = created.json()
    assert row["created_at"].endswith("Z")
    thread = row["thread_id"]
    with api.db() as db:
        assert db.get(ChatConversation, thread).created_at.isoformat() == row["created_at"].rstrip("Z")
    assert client.get("/api/conversations", headers=headers).json()["items"][0]["thread_id"] == thread
    assert client.get(f"/api/conversations/{thread}/messages", headers=headers).json()["messages"] == []
    for other in ("bobby", "admin", "carol"):
        other_headers = api.headers(other)
        assert client.get("/api/conversations", headers=other_headers).json()["items"] == []
        for method, suffix, body in [
            ("get", "/messages", None), ("delete", "", None),
            ("post", "/messages", {"question": "hello"}),
            ("post", "/resume", {"confirmation_id": "bad", "confirmed": True}),
            ("post", "/feedback", {"message_id": "bad", "feedback": "up"}),
        ]:
            kwargs = {"headers": other_headers}
            if body is not None:
                kwargs["json"] = body
            response = client.request(method, f"/api/conversations/{thread}{suffix}", **kwargs)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    assert client.delete(f"/api/conversations/{thread}", headers=headers).status_code == 204
    for identifier in (thread, str(uuid4())):
        result = client.get(f"/api/conversations/{identifier}/messages", headers=headers)
        assert result.status_code == 404
        assert result.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    assert client.post(f"/api/conversations/{thread}/messages", headers=headers, json={"question": "resurrect"}).status_code == 404


def test_input_and_limits(api):
    client, headers = api.client, api.headers()
    assert client.post("/api/conversations", headers=headers, json={"owner_user_id": api.users["admin"]}).status_code == 422
    assert client.get("/api/conversations?limit=51", headers=headers).status_code == 422
    assert client.get("/api/conversations?limit=0", headers=headers).status_code == 422
    for identifier in ("bad.id", "bad%20id", "a" * 37):
        assert client.get(f"/api/conversations/{identifier}/messages", headers=headers).status_code == 422
    assert client.get("/api/conversations/not-a-uuid/messages", headers=headers).status_code == 404


def test_legacy_id_list_history_resume_feedback_and_delete(api):
    """Legacy ownership/keys are preserved across every conversation endpoint."""
    thread = "test-cart"
    with api.db() as db:
        db.add(ChatConversation(thread_id=thread, owner_user_id=api.users["admin"]))
        db.commit()
    headers = api.headers("admin")
    client = api.client
    assert client.get("/api/conversations", headers=headers).json()["items"][0]["thread_id"] == thread
    empty = client.get(f"/api/conversations/{thread}/messages", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["thread_id"] == thread

    for name in ("alice", "bobby", "carol"):
        other = api.headers(name)
        assert client.get("/api/conversations", headers=other).json()["items"] == []
        for method, suffix, body in [
            ("GET", "/messages", None), ("DELETE", "", None),
            ("POST", "/messages", {"question": "hello"}),
            ("POST", "/resume", {"confirmation_id": "not-owned", "confirmed": False}),
            ("POST", "/feedback", {"message_id": "not-owned", "feedback": "up"}),
        ]:
            kwargs = {"headers": other}
            if body is not None:
                kwargs["json"] = body
            assert client.request(method, f"/api/conversations/{thread}{suffix}", **kwargs).status_code == 404

    answer = client.post(f"/api/conversations/{thread}/messages", headers=headers, json={"question": "hello"})
    assert answer.status_code == 200
    assert answer.json()["thread_id"] == thread
    message_id = answer.json()["message"]["id"]
    assert client.post(f"/api/conversations/{thread}/feedback", headers=headers,
                       json={"message_id": message_id, "feedback": "up"}).status_code == 201
    pending = client.post(f"/api/conversations/{thread}/messages", headers=headers, json={"question": "rank"})
    confirmation_id = pending.json()["pending_confirmations"][0]["confirmation_id"]
    resumed = client.post(f"/api/conversations/{thread}/resume", headers=headers,
                          json={"confirmation_id": confirmation_id, "confirmed": False})
    assert resumed.status_code == 200
    assert client.delete(f"/api/conversations/{thread}", headers=headers).status_code == 204
    assert client.get(f"/api/conversations/{thread}/messages", headers=headers).status_code == 404


def test_cleanup_failure_retry_and_feedback_removed(api, monkeypatch):
    thread = api.create()
    result = api.client.post(f"/api/conversations/{thread}/messages", headers=api.headers(), json={"question": "hello"})
    message = result.json()["message"]["id"]
    assert api.client.post(f"/api/conversations/{thread}/feedback", headers=api.headers(),
                           json={"message_id": message, "feedback": "up"}).status_code == 201
    real_delete = checkpoints.delete_checkpoints
    def fail(_):
        raise sqlite3.OperationalError("SECRET path")
    monkeypatch.setattr(checkpoints, "delete_checkpoints", fail)
    response = api.client.delete(f"/api/conversations/{thread}", headers=api.headers())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CONVERSATION_CLEANUP_PENDING"
    assert "SECRET" not in response.text
    assert api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers()).status_code == 404
    with api.db() as db:
        assert db.get(ChatConversation, thread).deleted_at is not None
        assert db.query(ChatFeedback).filter_by(thread_id=thread).count() == 0
    monkeypatch.setattr(checkpoints, "delete_checkpoints", real_delete)
    assert api.client.delete(f"/api/conversations/{thread}", headers=api.headers("bobby")).status_code == 404
    assert api.client.delete(f"/api/conversations/{thread}", headers=api.headers()).status_code == 204
    assert api.saver.get_tuple({"configurable": {"thread_id": thread}}) is None


def test_history_provider_independent_and_storage_errors(api, monkeypatch):
    thread = api.create()
    def fail(*a, **k):
        raise AssertionError("Provider must not be initialized")
    monkeypatch.setattr(api.router, "_get_graph", fail)
    import src.agent.agent_executor as executor
    monkeypatch.setattr(executor, "get_prompt_text", fail)
    monkeypatch.setattr(executor, "ChatGoogleGenerativeAI", fail)
    monkeypatch.setattr(checkpoints, "_reader", None)
    response = api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers())
    assert response.status_code == 200
    def broken(_):
        raise sqlite3.OperationalError("password=SECRET")
    monkeypatch.setattr(checkpoints, "read_state", broken)
    response = api.client.get(f"/api/conversations/{thread}/messages", headers=api.headers())
    assert response.status_code == 503
    assert "SECRET" not in response.text
