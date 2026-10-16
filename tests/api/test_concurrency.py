from concurrent.futures import ThreadPoolExecutor
from src.chat import concurrency
from src.auth import service as auth
from src.retrieval.access_scope import current_department_id


def test_busy_ask_resume_delete_feedback_and_status(api):
    thread = api.create()
    prefix = f"/api/conversations/{thread}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(api.client.post, prefix + "/messages", headers=api.headers(), json={"question": "wait"})
        assert api.started.wait(5)
        try:
            state = api.client.get(prefix + "/messages", headers=api.headers()).json()
            assert state["execution_status"] == "running"
            for method, suffix, body in [
                ("post", "/messages", {"question": "duplicate"}),
                ("post", "/resume", {"confirmation_id": "id", "confirmed": True}),
                ("post", "/feedback", {"message_id": "id", "feedback": "up"}),
                ("delete", "", None),
            ]:
                response = api.client.request(method, prefix + suffix, headers=api.headers(), **({"json": body} if body else {}))
                assert response.status_code == 409
                assert response.json()["error"]["code"] == "CONVERSATION_BUSY"
            # Do not leak busy state to another owner.
            assert api.client.delete(prefix, headers=api.headers("bobby")).status_code == 404
        finally:
            api.release.set()
        assert running.result(timeout=10).status_code == 200
    assert not concurrency.is_running(thread)
    assert thread not in concurrency._locks


def test_two_requests_preserve_context_through_real_tools(api):
    first, second = api.create("alice"), api.create("carol")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(api.client.post, f"/api/conversations/{thread}/messages",
                               headers=api.headers(name), json={"question": "hello"})
                   for thread, name in ((first, "alice"), (second, "carol"))]
        assert [f.result(timeout=10).status_code for f in futures] == [200, 200]
    assert set(api.observations) == {("alice", "tester", "dept-a"), ("carol", "tester", "dept-b")}
    assert auth._token.get() is None
    assert current_department_id.get() is None


def test_delete_cannot_race_feedback_insert(api, monkeypatch):
    from threading import Event
    from src.chat import feedback_store
    from src.db.models import ChatFeedback
    entered, release = Event(), Event()
    thread = api.create()
    prefix = f"/api/conversations/{thread}"
    answer = api.client.post(prefix + "/messages", headers=api.headers(),
                             json={"question": "hello"}).json()["message"]
    save = feedback_store.save_feedback

    def delayed_save(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return save(*args, **kwargs)

    monkeypatch.setattr(feedback_store, "save_feedback", delayed_save)
    with ThreadPoolExecutor(max_workers=1) as pool:
        vote = pool.submit(api.client.post, prefix + "/feedback", headers=api.headers(),
                           json={"message_id": answer["id"], "feedback": "up"})
        assert entered.wait(5)
        try:
            assert api.client.delete(prefix, headers=api.headers()).status_code == 409
        finally:
            release.set()
        assert vote.result(timeout=5).status_code == 201
    assert api.client.delete(prefix, headers=api.headers()).status_code == 204
    with api.db() as db:
        assert db.query(ChatFeedback).filter_by(thread_id=thread).count() == 0
