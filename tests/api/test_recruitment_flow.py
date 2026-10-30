"""One integrated business flow; only model, storage, broker and Gmail are fakes."""
import importlib
from uuid import uuid4

import fitz
from sqlalchemy import func, select

from src.db.models import AppUser, Candidate, CandidateChunk
from src.ingestion import pipeline
from src.schemas.cv_schema import CVSchema
from src.schemas.interview_question_schema import InterviewCategory, InterviewQuestion, QuestionList
from src.workers import tasks_ingestion
from tests.api.test_management_ingestion import intake, upload  # noqa: F401
from tests.api.test_emails import emails, create, generate, dispatch, get, worker  # noqa: F401


def test_upload_to_scoped_ranking_interview_and_approved_email_history(intake, emails, monkeypatch):
    api = intake.api
    raw = "Built Python and SQL pipelines. Designed APIs. Mentored engineers. " * 4
    with fitz.open() as pdf:
        pdf.new_page().insert_textbox((40, 40, 550, 700), "Demo Candidate\n" + raw)
        intake.data = pdf.tobytes() + b"\n%" + b"a" * 22000
    monkeypatch.setattr(pipeline, "classify_is_cv", lambda text: type("Classification", (), {"is_cv": True, "confidence": 1})())
    monkeypatch.setattr(pipeline, "extract_cv_data", lambda text: CVSchema(full_name="Demo Candidate", email="demo@example.test",
        applied_position="Backend", total_years_experience=3, skills=["Python", "SQL"]))
    indexed = []
    class Vectors:
        def ensure_collection(self): pass
        def delete_by_candidate(self, identifier): pass
        def upsert_chunks(self, ids, vectors, payloads): indexed.extend(payloads)
    monkeypatch.setattr(pipeline, "QdrantStore", Vectors)
    monkeypatch.setattr(pipeline, "embed_texts", lambda texts: [[0.0] * 768 for text in texts])
    accepted = upload(intake)
    assert accepted.status_code == 202, accepted.text
    job = accepted.json()["job_id"]
    tasks_ingestion.process_cv_job.run(job)
    state = api.client.get(f"/api/ingestion/jobs/{job}", headers=api.headers("admin")).json()
    assert state["status"] == "indexed"
    cid = state["candidate_id"]
    assert indexed and all(p["candidate_id"] == cid for p in indexed)
    with api.db() as db:
        assert db.scalar(select(func.count()).select_from(CandidateChunk).where(CandidateChunk.candidate_id == cid)) == len(indexed)
        assert db.get(Candidate, cid).posting_id == intake.post
        db.query(AppUser).filter_by(username="alice").one().department_id = intake.dept
        db.commit()
    assert upload(intake).json()["job_id"] == job
    assert api.client.get("/api/candidates?q=Demo%20Candidate", headers=api.headers("alice")).json()["total"] == 1
    assert api.client.get("/api/candidates?q=Demo%20Candidate", headers=api.headers("carol")).json()["total"] == 0
    assert api.client.get(f"/api/candidates/{cid}", headers=api.headers("carol")).status_code == 404

    tool = importlib.import_module("src.agent.tools.jd_matching_tool")
    monkeypatch.setattr(tool, "rank_candidates_for_jd", lambda jd, top_k: [{"candidate_id": cid, "overall_score": 4.5,
        "summary": "Python and SQL experience", "criteria": [], "strengths": ["Python"], "concerns": []}])
    thread = api.create("admin")
    path = f"/api/conversations/{thread}"
    pending = api.client.post(path + "/messages", headers=api.headers("admin"), json={"question": "rank one"}).json()
    ranked = api.client.post(path + "/resume", headers=api.headers("admin"), json={
        "confirmation_id": pending["pending_confirmations"][0]["confirmation_id"], "confirmed": True})
    assert ranked.status_code == 200, ranked.text
    assert ranked.json()["message"]["candidate_results"][0]["items"][0]["candidate_id"] == cid
    assert api.client.get(path + "/messages", headers=api.headers("alice")).status_code == 404

    from src.interview import question_generator
    monkeypatch.setattr(question_generator, "call_with_key_failover", lambda fn: fn("test-key"))
    monkeypatch.setattr(question_generator, "_generate_call", lambda *args: QuestionList(questions=[
        InterviewQuestion(question="How did you build the pipelines? " + category.value, category=category,
            evidence_quote="Built Python and SQL pipelines.", cv_section="Experience") for category in InterviewCategory]))
    endpoint = f"/api/candidates/{cid}/interview-questions"
    revision = api.client.get(endpoint, headers=api.headers("admin")).json()["revision"]
    response = api.client.post(endpoint + "/generate", headers=api.headers("admin"), json={"expected_revision": revision, "max_questions": 3})
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 3
    assert api.client.get(endpoint, headers=api.headers("alice")).status_code == 403

    batch = generate(emails, create(emails, ids=[cid], request_id=str(uuid4())))
    assert not emails.sent
    approved = dispatch(emails, batch)
    assert approved.status_code == 202, approved.text
    worker.process_batch(batch["batch_id"])
    worker.process_batch(batch["batch_id"])
    assert len(emails.sent) == 1 and emails.sent[0]["to"] == "demo@example.test"
    assert get(emails, batch["batch_id"])["counts"]["success"] == 1
    history = api.client.get("/api/emails/history", headers=api.headers("admin")).json()
    assert history["items"][0]["candidate_id"] == cid
    assert api.client.get("/api/emails/history", headers=api.headers("alice")).status_code == 403


def test_tester_cannot_read_admin_endpoints_by_direct_url(api):
    cid = str(uuid4())
    for path in ("/api/admin/users", "/api/admin/departments", "/api/admin/postings", "/api/ingestion/capabilities",
                 "/api/ingestion/jobs", "/api/ops/dashboard", "/api/ops/optimization", "/api/emails/batches",
                 "/api/emails/history", f"/api/candidates/{cid}/interview-questions"):
        assert api.client.get(path).status_code == 401, path
        assert api.client.get(path, headers=api.headers("alice")).status_code == 403, path
