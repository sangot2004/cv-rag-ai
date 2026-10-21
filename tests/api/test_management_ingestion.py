import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import fitz
import pytest
from src.auth import service as auth
from src.db.models import Candidate, Department, IngestionJob, JobPosting, ChatConversation
from src.ingestion import jobs, pipeline
from src.workers import tasks_ingestion as worker
from src.schemas.cv_schema import CVSchema


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def intake(api, monkeypatch):
    monkeypatch.setattr(worker, "SessionLocal", api.db)
    monkeypatch.setattr(pipeline, "SessionLocal", api.db)
    dept, post = uid(), uid()
    with api.db() as db:
        db.add(Department(department_id=dept, department_name="Engineering"))
        db.flush()
        db.add(JobPosting(posting_id=post, department_id=dept, position_title="Backend"))
        db.commit()
    objects, published = {}, []
    class Storage:
        bucket = "private-bucket"
        @staticmethod
        def build_object_key(job_id, name): return job_id + "/" + name
        def upload_bytes(self, key, data, **kwargs): objects[key] = data
        def download_bytes(self, key): return objects[key]
    monkeypatch.setattr(jobs, "storage_client", Storage)
    monkeypatch.setattr(pipeline, "MinioStorage", Storage)
    from src.workers.celery_app import celery_app
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **kw: published.append(kw["args"][0]))
    with fitz.open() as doc:
        doc.new_page().insert_text((40,40), "Candidate CV Python")
        data = doc.tobytes() + b"\n%" + b"a" * 22000
    return SimpleNamespace(api=api, dept=dept, post=post, objects=objects, published=published, data=data)


def upload(f, **kwargs):
    return f.api.client.post("/api/ingestion/uploads", headers=f.api.headers("admin"),
        files={"file": (kwargs.pop("filename", "NguyenVanA_Backend_CV.pdf"), kwargs.pop("data", f.data), "application/pdf")},
        data={"posting_id": kwargs.pop("posting", f.post)}, **kwargs)


def test_management_counts_filters_and_authorization(intake):
    f, api = intake, intake.api
    for path in ("/api/admin/users", "/api/admin/departments", "/api/admin/postings", "/api/ingestion/jobs", "/api/ingestion/capabilities"):
        assert api.client.get(path).status_code == 401
        assert api.client.get(path, headers=api.headers()).status_code == 403
    response = api.client.post("/api/admin/departments", headers=api.headers("admin"), json={"department_name": " Sales "})
    assert response.status_code == 201
    dept = response.json()["department_id"]
    assert api.client.post("/api/admin/departments", headers=api.headers("admin"), json={"department_name": "sales"}).status_code == 409
    post = api.client.post("/api/admin/postings", headers=api.headers("admin"), json={"department_id": dept, "position_title": "Sales Engineer"}).json()["posting_id"]
    rows = api.client.get("/api/admin/postings", headers=api.headers("admin"), params={"department_id": dept}).json()
    assert [r["posting_id"] for r in rows["items"]] == [post]
    assert api.client.get("/api/admin/departments?q=%25", headers=api.headers("admin")).json()["total"] == 0
    assert api.client.get("/api/admin/users?page_size=2", headers=api.headers("admin")).json()["has_next"]
    assert api.client.get("/api/admin/users?role=tester&active=true", headers=api.headers("admin")).json()["total"] == 3
    assert api.client.get("/api/admin/postings?unknown=x", headers=api.headers("admin")).status_code == 422


def test_create_lock_reenable_account_revokes_sessions_but_keeps_history(intake):
    api, dept = intake.api, intake.dept
    body = dict(username="new_tester", password="long-password-123", role="tester", department_id=dept)
    r = api.client.post("/api/admin/users", headers=api.headers("admin"), json=body)
    assert r.status_code == 201, r.text
    identifier = r.json()["user_id"]
    assert "password" not in r.text and "scrypt" not in r.text
    signed = api.client.post("/api/auth/login", json={"username": body["username"], "password": body["password"]})
    headers = {"Authorization": "Bearer " + signed.json()["access_token"]}
    thread = api.client.post("/api/conversations", headers=headers, json={}).json()["thread_id"]
    for active in (False, True):
        r = api.client.post(f"/api/admin/users/{identifier}/active", headers=api.headers("admin"), json={"active": active})
        assert r.status_code == 200
        assert api.client.get("/api/auth/me", headers=headers).status_code == 401
    with api.db() as db:
        assert db.get(ChatConversation, thread).owner_user_id == identifier
    assert api.client.post("/api/auth/login", json={"username": body["username"], "password": body["password"]}).status_code == 200
    assert api.client.post(f"/api/admin/users/{api.users['admin']}/active", headers=api.headers("admin"), json={"active": False}).status_code == 409
    for bad in [dict(body, department_id=None), dict(body, password="short"), dict(body, role="root")]:
        rejected = api.client.post("/api/admin/users", headers=api.headers("admin"), json=bad)
        assert rejected.status_code == 422
        assert "short" not in rejected.text and "password-123" not in rejected.text


def test_upload_replay_validation_projection_queue_outage_and_requeue(intake, monkeypatch):
    f, api = intake, intake.api
    from src.workers.celery_app import celery_app
    def down(*a, **kw): raise RuntimeError("secret-provider-key")
    monkeypatch.setattr(celery_app, "send_task", down)
    r = upload(f)
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["dispatch_error"] == "QUEUE_UNAVAILABLE" and job["status"] == "pending"
    assert not any(s in r.text for s in ("minio", "private-bucket", "secret-provider-key", "file_hash"))
    assert upload(f).json()["job_id"] == job["job_id"] and len(f.objects) == 1
    assert api.client.get("/api/ingestion/jobs?source_type=web_upload", headers=api.headers("admin")).json()["total"] == 1
    monkeypatch.setattr(celery_app, "send_task", lambda *a, **kw: f.published.append(kw["args"][0]))
    retry = api.client.post(f"/api/ingestion/jobs/{job['job_id']}/retry", headers=api.headers("admin"), json={"confirmed": True})
    assert retry.status_code == 202 and retry.json()["dispatch_error"] is None
    assert f.published == [job["job_id"]]
    assert upload(f, filename="../../private.pdf").status_code == 422
    assert upload(f, filename="bad.txt").status_code == 422
    assert upload(f, data=b"tiny").status_code == 422
    assert upload(f, data=b"bad" * 8000).status_code == 422
    assert upload(f, posting=uid()).status_code == 422
    assert api.client.post("/api/ingestion/uploads", headers=api.headers(), files={"file": ("a.pdf", f.data)}).status_code == 403
    with api.db() as db:
        row = db.get(IngestionJob, job["job_id"])
        row.status, row.error_message = "rejected", "provider-key=SECRET"
        db.commit()
    legacy = api.client.get(f"/api/ingestion/jobs/{job['job_id']}", headers=api.headers("admin"))
    assert "SECRET" not in legacy.text and legacy.json()["error_code"] == "CV_REJECTED"
    assert api.client.post(f"/api/ingestion/jobs/{job['job_id']}/retry", headers=api.headers("admin"), json={"confirmed": True}).status_code == 409


def test_explicit_assignment_atomic_change_and_scope(intake, monkeypatch):
    f, api = intake, intake.api
    job = upload(f).json()["job_id"]
    candidate = uid()
    with api.db() as db:
        db.add(Candidate(candidate_id=candidate, full_name="Ada", source_job_id=job))
        db.commit()
    endpoint = f"/api/candidates/{candidate}/posting"
    assert api.client.post(endpoint, headers=api.headers(), json={"posting_id": f.post, "expected_posting_id": None}).status_code == 403
    assert api.client.post(endpoint, headers=api.headers("admin"), json={"posting_id": f.post, "expected_posting_id": None}).status_code == 200
    assert api.client.post(endpoint, headers=api.headers("admin"), json={"posting_id": None, "expected_posting_id": None}).status_code == 409
    depts = api.client.get("/api/admin/departments?q=Engineering", headers=api.headers("admin")).json()["items"]
    assert depts[0]["cv_count"] == 1 and depts[0]["posting_count"] == 1
    from src.retrieval import sql_query_tool as sql
    from src.retrieval.access_scope import department_scope
    monkeypatch.setattr(sql, "SessionLocal", api.db)
    with department_scope(f.dept):
        assert candidate in sql.get_allowed_candidate_ids()
    with department_scope("dept-b"):
        assert candidate not in sql.get_allowed_candidate_ids()
    assert api.client.post(endpoint, headers=api.headers("admin"), json={"posting_id": None, "expected_posting_id": f.post}).status_code == 200
    with department_scope(f.dept):
        assert candidate not in sql.get_allowed_candidate_ids()


def mock_pipeline(monkeypatch):
    raw = "CV candidate Python data engineer. " * 20
    monkeypatch.setattr(pipeline, "extract_text_from_pdf", lambda data: raw)
    monkeypatch.setattr(pipeline, "classify_is_cv", lambda raw: SimpleNamespace(is_cv=True, confidence=1))
    monkeypatch.setattr(pipeline, "extract_cv_data", lambda raw: CVSchema(full_name="Ada", applied_position="Sales"))
    monkeypatch.setattr(pipeline, "extract_portrait_photo", lambda data: None)
    monkeypatch.setattr(pipeline, "build_documents_from_cv", lambda *a: [])
    return raw


def test_worker_preserves_explicit_posting_indexes_once_and_blocks_live_recovery(intake, monkeypatch):
    f, api = intake, intake.api
    raw = mock_pipeline(monkeypatch)
    identifier = upload(f).json()["job_id"]
    entered, release = Event(), Event()
    def extract(raw):
        entered.set(); assert release.wait(10)
        return CVSchema(full_name="Ada", applied_position="Sales")
    monkeypatch.setattr(pipeline, "extract_cv_data", extract)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(worker.process_cv_job.run, identifier)
        assert entered.wait(10)
        second = pool.submit(worker.process_cv_job.run, identifier)
        second.result(5)
        r = api.client.post(f"/api/ingestion/jobs/{identifier}/retry", headers=api.headers("admin"), json={"confirmed": True})
        assert r.status_code == 409 and r.json()["error"]["code"] == "JOB_RUNNING"
        release.set(); first.result(10)
    worker.process_cv_job.run(identifier)
    with api.db() as db:
        job = db.get(IngestionJob, identifier)
        assert job.status == "indexed" and job.attempts == 1
        cv = db.get(Candidate, job.candidate_id)
        assert cv.posting_id == f.post and cv.content_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert db.query(Candidate).count() == 1


def test_worker_errors_rejection_dlq_and_recovery(intake, monkeypatch):
    f, api = intake, intake.api
    identifier = upload(f).json()["job_id"]
    def fail(job): raise RuntimeError("secret-url-password")
    monkeypatch.setattr(worker, "run_ingestion_pipeline", fail)
    monkeypatch.setattr(worker.process_cv_job, "retry", lambda **kw: RuntimeError("scheduled"))
    for _ in range(2):
        with pytest.raises(RuntimeError, match="scheduled"): worker.process_cv_job.run(identifier)
    worker.process_cv_job.run(identifier)
    with api.db() as db:
        row = db.get(IngestionJob, identifier)
        assert row.status == "dlq" and row.attempts == 3 and "secret" not in row.error_message
    r = api.client.post(f"/api/ingestion/jobs/{identifier}/retry", headers=api.headers("admin"), json={"confirmed": True})
    assert r.json()["status"] == "pending" and r.json()["attempts"] == 0
    def reject(job): raise pipeline.CVRejected("not_a_cv: private data")
    monkeypatch.setattr(worker, "run_ingestion_pipeline", reject)
    worker.process_cv_job.run(identifier)
    assert api.client.get(f"/api/ingestion/jobs/{identifier}", headers=api.headers("admin")).json()["status"] == "rejected"


def test_pdf_page_encryption_limits_and_safe_storage_failure(intake, monkeypatch):
    f = intake
    with fitz.open() as doc:
        for _ in range(11): doc.new_page()
        data = doc.tobytes() + b"\n%" + b"a" * 22000
    r = upload(f, data=data)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PDF_TOO_MANY_PAGES"
    def broken(): raise RuntimeError("minio-secret-password")
    monkeypatch.setattr(jobs, "storage_client", broken)
    r = upload(f)
    assert r.status_code == 503 and "minio-secret" not in r.text


def test_file_replay_different_posting_conflicts_and_stopped_worker_recovery(intake):
    f, api = intake, intake.api
    identifier = upload(f).json()["job_id"]
    posting = api.client.post("/api/admin/postings", headers=api.headers("admin"), json={"department_id": f.dept, "position_title": "Data"}).json()["posting_id"]
    assert upload(f, posting=posting).status_code == 409
    with api.db() as db:
        job = db.get(IngestionJob, identifier)
        job.status, job.attempts = "processing", 1
        db.commit()
    r = api.client.post(f"/api/ingestion/jobs/{identifier}/retry", headers=api.headers("admin"), json={"confirmed": True})
    assert r.status_code == 202 and r.json()["status"] == "pending"


def test_migration_0014_preserves_old_jobs(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as conn:
        for table, column in (("app_users", "user_id"), ("job_postings", "posting_id")):
            conn.execute(text(f"CREATE TABLE {table} ({column} CHAR(36) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE ingestion_jobs (job_id CHAR(36) PRIMARY KEY, status VARCHAR(20))"))
        conn.execute(text("INSERT INTO ingestion_jobs(job_id,status) VALUES ('old','indexed')"))
        spec = importlib.util.spec_from_file_location("ingestion_migration", "alembic/versions/add_ingestion_management.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert conn.execute(text("SELECT status, file_hash, posting_id FROM ingestion_jobs WHERE job_id='old'")).one() == ("indexed", None, None)
            module.downgrade()
            assert {column["name"] for column in inspect(conn).get_columns("ingestion_jobs")} == {"job_id", "status"}
            assert conn.execute(text("SELECT status FROM ingestion_jobs WHERE job_id='old'")).scalar_one() == "indexed"
    engine.dispose()
