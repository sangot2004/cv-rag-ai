from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from src.auth import service as auth
from src.auth.errors import AuthenticationRequired, Forbidden
from src.db.models import AppUser, Candidate, IngestionJob, InterviewQuestion
from src.interview import question_generator as generator, service
from src.schemas.interview_question_schema import InterviewCategory, InterviewQuestion as GeneratedQuestion, QuestionList


@pytest.fixture
def interviews(api, monkeypatch):
    ids = [str(uuid4()), str(uuid4())]
    with api.db() as db:
        for index, candidate_id in enumerate(ids):
            job_id = str(uuid4())
            db.add(IngestionJob(job_id=job_id, source_type="upload", source_reference="test",
                minio_bucket="private", minio_object_key="private/cv.pdf", original_filename="cv.pdf", file_type="pdf"))
            db.flush()
            db.add(Candidate(candidate_id=candidate_id, full_name=f"Person {index}", source_job_id=job_id,
                raw_text="Built Python and SQL pipelines. Designed APIs. Mentored engineers." if index == 0 else None))
        db.commit()
    calls = []
    def answer(key, cv_text, max_questions):
        calls.append((cv_text, max_questions))
        return QuestionList(questions=[GeneratedQuestion(question=f"Question {category.value}", category=category,
            evidence_quote="Built Python and SQL pipelines.", cv_section="Experience") for category in InterviewCategory])
    monkeypatch.setattr(generator, "call_with_key_failover", lambda fn: fn("test-key"))
    monkeypatch.setattr(generator, "_generate_call", answer)
    return api, ids, calls


def url(candidate_id):
    return f"/api/candidates/{candidate_id}/interview-questions"


def read(api, candidate_id):
    response = api.client.get(url(candidate_id), headers=api.headers("admin"))
    assert response.status_code == 200, response.text
    return response.json()


def generate(api, candidate_id, state, **kwargs):
    return api.client.post(url(candidate_id) + "/generate", headers=api.headers("admin"),
        json={"expected_revision": state["revision"], "max_questions": 3, **kwargs})


def test_read_generate_replace_and_delete_persisted_set(interviews):
    api, (candidate_id, _), calls = interviews
    initial = read(api, candidate_id)
    assert initial["items"] == [] and initial["has_cv"] and not initial["is_generating"]
    response = generate(api, candidate_id, initial)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    saved = response.json()
    assert len(saved["items"]) == 3 and saved["revision"] != initial["revision"]
    assert saved == read(api, candidate_id)
    assert {q["category"] for q in saved["items"]} == {c.value for c in InterviewCategory}
    assert all(q["id"] > 0 and q["evidence_quote"] for q in saved["items"])
    assert calls[0][1] == 3
    assert generate(api, candidate_id, saved).json()["error"]["code"] == "INTERVIEW_REPLACE_REQUIRED"
    assert len(calls) == 1
    replaced = generate(api, candidate_id, saved, replace_existing=True)
    assert replaced.status_code == 200
    state = read(api, candidate_id)
    missing = api.client.delete(url(candidate_id), headers=api.headers("admin"))
    assert missing.status_code == 422
    deleted = api.client.delete(url(candidate_id), headers=api.headers("admin"), params={"expected_revision": state["revision"]})
    assert deleted.status_code == 200 and deleted.json()["items"] == []
    assert read(api, candidate_id)["items"] == []


def test_permissions_missing_candidate_and_empty_cv(interviews):
    api, (candidate_id, no_cv_id), calls = interviews
    for path, method, data in [(url(candidate_id), "GET", None), (url(candidate_id), "DELETE", None),
        (url(candidate_id)+"/generate", "POST", {"expected_revision": "a"*64})]:
        kwargs = {"json": data} if data else {}
        if method == "DELETE": kwargs["params"] = {"expected_revision": "a"*64}
        assert api.client.request(method, path, **kwargs).status_code == 401
        assert api.client.request(method, path, headers=api.headers("alice"), **kwargs).status_code == 403
    assert not calls
    assert api.client.get(url(str(uuid4())), headers=api.headers("admin")).status_code == 404
    assert api.client.get(url("invalid"), headers=api.headers("admin")).status_code == 422
    empty = read(api, no_cv_id)
    assert empty["has_cv"] is False
    response = generate(api, no_cv_id, empty)
    assert response.status_code == 422 and response.json()["error"]["code"] == "CANDIDATE_HAS_NO_CV"
    with pytest.raises(AuthenticationRequired): service.get_questions(candidate_id)
    with auth.auth_scope(api.tokens["alice"]), pytest.raises(Forbidden): service.get_questions(candidate_id)
    assert not calls


@pytest.mark.parametrize("extra", [{"max_questions": 2}, {"max_questions": 16}, {"max_questions": True}, {"max_questions": "8"},
    {"expected_revision": "invalid"}, {"replace_existing": "true"}, {"role": "admin"}])
def test_strict_generation_input(interviews, extra):
    api, (candidate_id, _), calls = interviews
    response = generate(api, candidate_id, read(api, candidate_id), **extra)
    assert response.status_code == 422
    assert not calls


def test_failed_and_invalid_generation_preserves_previous_set(interviews, monkeypatch):
    api, (candidate_id, _), _ = interviews
    saved = generate(api, candidate_id, read(api, candidate_id)).json()
    attempts = []
    def bad(*args):
        attempts.append(1)
        return QuestionList(questions=[GeneratedQuestion(question="Invalid", category=InterviewCategory.TECHNICAL,
            cv_section="Experience", evidence_quote=" ")])
    monkeypatch.setattr(generator, "_generate_call", bad)
    response = generate(api, candidate_id, saved, replace_existing=True)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_VALID_INTERVIEW_QUESTIONS"
    assert len(attempts) == 2
    assert read(api, candidate_id) == saved
    def fail(*args): raise TimeoutError("private-key=SECRET")
    monkeypatch.setattr(generator, "_generate_call", fail)
    response = generate(api, candidate_id, saved, replace_existing=True)
    assert response.status_code == 504 and "SECRET" not in response.text
    assert read(api, candidate_id) == saved


def test_stale_cv_or_set_is_rejected_before_and_after_model_call(interviews, monkeypatch):
    api, (candidate_id, _), calls = interviews
    before = read(api, candidate_id)
    saved = generate(api, candidate_id, before).json()
    assert generate(api, candidate_id, before, replace_existing=True).status_code == 409
    assert api.client.delete(url(candidate_id), headers=api.headers("admin"), params={"expected_revision": before["revision"]}).status_code == 409
    answer = generator._generate_call
    def change_cv(*args):
        with api.db() as db:
            db.get(Candidate, candidate_id).raw_text += " New CV content."
            db.commit()
        return answer(*args)
    monkeypatch.setattr(generator, "_generate_call", change_cv)
    response = generate(api, candidate_id, saved, replace_existing=True)
    assert response.status_code == 409 and response.json()["error"]["code"] == "STALE_INTERVIEW_SET"
    assert read(api, candidate_id)["items"] == saved["items"]
    assert len(calls) == 2


def test_concurrent_requests_read_progress_and_cannot_overwrite(interviews, monkeypatch):
    api, (candidate_id, _), calls = interviews
    state = read(api, candidate_id)
    started, release = Event(), Event()
    answer = generator._generate_call
    def blocking(*args):
        started.set()
        assert release.wait(10)
        return answer(*args)
    monkeypatch.setattr(generator, "_generate_call", blocking)
    with ThreadPoolExecutor() as executor:
        future = executor.submit(generate, api, candidate_id, state)
        try:
            assert started.wait(5)
            assert read(api, candidate_id)["is_generating"] is True
            assert generate(api, candidate_id, state).json()["error"]["code"] == "INTERVIEW_BUSY"
            assert api.client.delete(url(candidate_id), headers=api.headers("admin"), params={"expected_revision": state["revision"]}).status_code == 409
        finally: release.set()
        assert future.result().status_code == 200
    assert not read(api, candidate_id)["is_generating"]
    assert len(calls) == 1


def test_session_revoked_during_generation_does_not_write(interviews, monkeypatch):
    api, (candidate_id, _), _ = interviews
    state = generate(api, candidate_id, read(api, candidate_id)).json()
    answer = generator._generate_call
    def revoke(*args):
        with api.db() as db:
            db.get(AppUser, api.users["admin"]).is_active = False
            db.commit()
        return answer(*args)
    monkeypatch.setattr(generator, "_generate_call", revoke)
    response = generate(api, candidate_id, state, replace_existing=True)
    assert response.status_code == 401
    with api.db() as db:
        rows = db.query(InterviewQuestion).filter_by(candidate_id=candidate_id).all()
        assert [row.question_text for row in rows] == [q["question"] for q in state["items"]]


def test_database_failure_rolls_back_replacement(interviews):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    api, (candidate_id, _), _ = interviews
    saved = generate(api, candidate_id, read(api, candidate_id)).json()
    def fail_insert(session, flush_context, instances):
        if any(isinstance(record, InterviewQuestion) for record in session.new):
            raise OperationalError("private SQL", {}, Exception("SECRET"))
    event.listen(api.db.class_, "before_flush", fail_insert)
    try:
        response = generate(api, candidate_id, saved, replace_existing=True)
        assert response.status_code == 503 and "SECRET" not in response.text
    finally:
        event.remove(api.db.class_, "before_flush", fail_insert)
    assert read(api, candidate_id) == saved
