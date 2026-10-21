from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.db.models import Candidate, IngestionJob, InvitationBatch, InvitationDelivery, InvitationDraft, SentEmail
from src.notification import delivery_worker as worker, invitations as inv
from src.schemas.email_draft_schema import EmailDraft


@pytest.fixture
def emails(api, monkeypatch):
    ids = [str(uuid4()) for _ in range(4)]
    with api.db() as db:
        for index, identifier in enumerate(ids):
            job_id = str(uuid4())
            db.add(IngestionJob(job_id=job_id, source_type="upload", source_reference="fixture", minio_bucket="private",
                minio_object_key="private.pdf", original_filename="cv.pdf", file_type="pdf"))
            db.flush()
            db.add(Candidate(candidate_id=identifier, source_job_id=job_id, full_name=f"Person {index}",
                email=["a@example.test", "b@example.test", None, "A@example.test"][index], raw_text="CV Python"))
        db.commit()
    from src.notification import email_drafter
    generated, sent, published = [], [], []
    def draft(candidate_id, position, details):
        generated.append((candidate_id, position, details))
        return EmailDraft(subject="Thư mời phỏng vấn", body="Xin chào, mời bạn phỏng vấn.\n" + details)
    monkeypatch.setattr(email_drafter, "draft_interview_email", draft)
    original_publish = inv.publish_batch
    monkeypatch.setattr(inv, "publish_batch", lambda identifier: published.append(identifier))
    class Gmail:
        def __init__(self, **kwargs): assert kwargs == {"interactive": False}
        def send_message(self, **payload): sent.append(payload); return "gmail-accepted"
        def find_sent_message(self, reference): return "gmail-accepted"
    monkeypatch.setattr(worker, "GmailClient", Gmail)
    return SimpleNamespace(api=api, ids=ids, generated=generated, sent=sent, published=published, publish=original_publish)


def create(ctx, ids=None, request_id=None, **changes):
    ids = ids or [ctx.ids[0]]
    data = {"kind": "single" if len(ids) == 1 else "bulk", "candidate_ids": ids,
        "request_id": request_id or str(uuid4()), "name": "Interview round", "position": "Data Engineer", "interview_details": "Ngày 2026-12-01, 10:00 UTC+7, tại văn phòng.", **changes}
    response = ctx.api.client.post("/api/emails/batches", headers=ctx.api.headers("admin"), json=data)
    assert response.status_code == 200, response.text
    return response.json()


def get(ctx, batch_id):
    response = ctx.api.client.get(f"/api/emails/batches/{batch_id}", headers=ctx.api.headers("admin"))
    assert response.status_code == 200, response.text
    return response.json()


def generate(ctx, batch):
    for draft in batch["drafts"]:
        response = ctx.api.client.post(f'/api/emails/drafts/{draft["draft_id"]}/generate',
            headers=ctx.api.headers("admin"), json={"expected_revision": draft["revision"]})
        assert response.status_code == 200, response.text
    return get(ctx, batch["batch_id"])


def dispatch(ctx, batch, **changes):
    body = {"confirmed": True, "allow_previous": False,
        "drafts": [{"draft_id": d["draft_id"], "revision": d["revision"]} for d in batch["drafts"]], **changes}
    return ctx.api.client.post(f'/api/emails/batches/{batch["batch_id"]}/dispatch', headers=ctx.api.headers("admin"), json=body)


def test_single_draft_preview_save_dispatch_delivery_history_and_idempotency(emails):
    ctx = emails
    request_id = str(uuid4())
    batch = create(ctx, request_id=request_id)
    assert create(ctx, request_id=request_id)["batch_id"] == batch["batch_id"]
    assert batch["status"] == "draft" and not batch["drafts"][0]["ready"]
    batch = generate(ctx, batch)
    draft = batch["drafts"][0]
    response = ctx.api.client.post(f'/api/emails/drafts/{draft["draft_id"]}', headers=ctx.api.headers("admin"),
        json={"expected_revision": draft["revision"], "subject": "HR reviewed", "body": "Nội dung đã duyệt"})
    assert response.status_code == 200
    batch = response.json()
    assert not ctx.sent and not ctx.published
    response = dispatch(ctx, batch)
    assert response.status_code == 202, response.text
    assert response.headers["cache-control"] == "private, no-store"
    queued = response.json()
    assert queued["total"] == 1 and queued["counts"]["queued"] == 1
    assert dispatch(ctx, batch).json()["deliveries"][0]["delivery_id"] == queued["deliveries"][0]["delivery_id"]
    assert len(ctx.published) == 1 and not ctx.sent
    worker.process_batch(batch["batch_id"])
    worker.process_batch(batch["batch_id"])
    assert len(ctx.sent) == 1 and ctx.sent[0]["subject"] == "HR reviewed"
    assert ctx.sent[0]["to"] == "a@example.test" and "rfc_message_id" in ctx.sent[0]
    done = get(ctx, batch["batch_id"])
    assert done["status"] == "completed" and done["counts"]["success"] == 1
    assert done["drafts"][0]["previously_sent"] is True
    history = ctx.api.client.get("/api/emails/history", headers=ctx.api.headers("admin")).json()
    assert history["total"] == 1 and history["items"][0]["status"] == "success"
    assert "body" not in history["items"][0]
    detail = ctx.api.client.get(f'/api/emails/history/{history["items"][0]["id"]}', headers=ctx.api.headers("admin")).json()
    assert detail["body"] == "Nội dung đã duyệt" and detail["gmail_message_id"] == "gmail-accepted"
    assert detail["sent_at"].endswith("Z")


def test_bulk_approval_sends_only_selected_frozen_saved_drafts(emails):
    ctx = emails; batch = generate(ctx, create(ctx, ctx.ids[:2]))
    approved = [batch["drafts"][0]]
    response = dispatch(ctx, batch, drafts=[{"draft_id": d["draft_id"], "revision": d["revision"]} for d in approved])
    assert response.status_code == 202
    d = batch["drafts"][1]
    edit = ctx.api.client.post(f'/api/emails/drafts/{d["draft_id"]}', headers=ctx.api.headers("admin"), json={"expected_revision": d["revision"], "subject": "changed", "body": "changed"})
    assert edit.status_code == 409
    worker.process_batch(batch["batch_id"])
    assert len(ctx.sent) == 1 and ctx.sent[0]["to"] == approved[0]["recipient_email"]
    assert get(ctx, batch["batch_id"])["total"] == 1
    assert dispatch(ctx, batch).status_code == 409  # A new selection is not a replay.


def test_stale_drafts_failed_ai_and_recipient_changes_preserve_content(emails, monkeypatch):
    ctx = emails; initial = create(ctx); batch = generate(ctx, initial); d = initial["drafts"][0]
    response = ctx.api.client.post(f'/api/emails/drafts/{d["draft_id"]}', headers=ctx.api.headers("admin"), json={"expected_revision": d["revision"], "subject": "stale", "body": "stale"})
    assert response.status_code == 409
    from src.notification import email_drafter
    def fail(*args): raise RuntimeError("SECRET API KEY")
    monkeypatch.setattr(email_drafter, "draft_interview_email", fail)
    d = batch["drafts"][0]
    response = ctx.api.client.post(f'/api/emails/drafts/{d["draft_id"]}/generate', headers=ctx.api.headers("admin"), json={"expected_revision": d["revision"]})
    assert response.status_code == 503 and "SECRET" not in response.text
    assert get(ctx, batch["batch_id"])["drafts"][0]["body"] == d["body"]
    with ctx.api.db() as db:
        db.get(Candidate, ctx.ids[0]).email = "changed@example.test"; db.commit()
    assert dispatch(ctx, batch).json()["error"]["code"] == "RECIPIENT_CHANGED"
    assert not ctx.sent


def test_duplicates_active_unknown_and_previous_success_are_guarded(emails):
    ctx = emails; batch = generate(ctx, create(ctx)); assert dispatch(ctx, batch).status_code == 202
    another = generate(ctx, create(ctx, [ctx.ids[3]]))
    assert dispatch(ctx, another).json()["error"]["code"] == "DELIVERY_UNRESOLVED"
    worker.process_batch(batch["batch_id"])
    assert dispatch(ctx, another).json()["error"]["code"] == "PREVIOUS_INVITATION"
    assert dispatch(ctx, another, allow_previous=True).status_code == 202
    worker.process_batch(another["batch_id"])
    assert len(ctx.sent) == 2
    dup = generate(ctx, create(ctx, [ctx.ids[0], ctx.ids[3]]))
    assert dispatch(ctx, dup, allow_previous=True).json()["error"]["code"] == "DUPLICATE_RECIPIENT"


def test_unknown_send_is_not_retried_and_reconciles_by_message_id(emails, monkeypatch):
    ctx = emails; batch = generate(ctx, create(ctx)); dispatch(ctx, batch)
    class Uncertain:
        def __init__(self, **kwargs): pass
        def send_message(self, **payload): ctx.sent.append(payload); raise TimeoutError("SECRET")
        def find_sent_message(self, reference):
            assert reference == ctx.sent[0]["rfc_message_id"]
            return "gmail-reconciled"
    monkeypatch.setattr(worker, "GmailClient", Uncertain)
    worker.process_batch(batch["batch_id"]); worker.process_batch(batch["batch_id"])
    state = get(ctx, batch["batch_id"]); delivery = state["deliveries"][0]
    assert delivery["status"] == "unknown" and len(ctx.sent) == 1
    response = ctx.api.client.post(f'/api/emails/deliveries/{delivery["delivery_id"]}/retry', headers=ctx.api.headers("admin"), json={"confirmed": True})
    assert response.status_code == 202 and response.json()["counts"]["unknown"] == 1
    response = ctx.api.client.post(f'/api/emails/deliveries/{delivery["delivery_id"]}/reconcile', headers=ctx.api.headers("admin"), json={"confirmed": True})
    assert response.status_code == 200 and response.json()["counts"]["success"] == 1
    worker.process_batch(batch["batch_id"]); assert len(ctx.sent) == 1


def test_setup_failure_can_be_explicitly_retried(emails, monkeypatch):
    ctx = emails; batch = generate(ctx, create(ctx)); dispatch(ctx, batch)
    good = worker.GmailClient
    def setup(**kwargs): raise RuntimeError("SECRET OAuth")
    monkeypatch.setattr(worker, "GmailClient", setup)
    worker.process_batch(batch["batch_id"])
    delivery = get(ctx, batch["batch_id"])["deliveries"][0]
    assert delivery["status"] == "failed" and delivery["error_code"] == "GMAIL_SETUP_FAILED"
    monkeypatch.setattr(worker, "GmailClient", good)
    response = ctx.api.client.post(f'/api/emails/deliveries/{delivery["delivery_id"]}/retry', headers=ctx.api.headers("admin"), json={"confirmed": True})
    assert response.status_code == 202
    worker.process_batch(batch["batch_id"])
    assert len(ctx.sent) == 1 and get(ctx, batch["batch_id"])["deliveries"][0]["attempts"] == 2


def test_logging_failure_after_send_does_not_cause_duplicate_and_stale_claim_is_unknown(emails, monkeypatch):
    ctx = emails; batch = generate(ctx, create(ctx)); dispatch(ctx, batch)
    finish = worker.finish
    def fail(*args, **kwargs): raise RuntimeError("DB unavailable after accepted send")
    monkeypatch.setattr(worker, "finish", fail)
    worker.process_batch(batch["batch_id"]); worker.process_batch(batch["batch_id"])
    assert len(ctx.sent) == 1
    state = get(ctx, batch["batch_id"]); delivery = state["deliveries"][0]
    assert delivery["status"] == "sending"
    with ctx.api.db() as db:
        db.get(InvitationDelivery, delivery["delivery_id"]).started_at = inv.now() - timedelta(minutes=11); db.commit()
    assert get(ctx, batch["batch_id"])["counts"]["unknown"] == 1  # No beat needed to expose recovery.
    history = ctx.api.client.get("/api/emails/history?status=unknown", headers=ctx.api.headers("admin")).json()
    assert history["total"] == 1 and history["items"][0]["status"] == "unknown"
    monkeypatch.setattr(worker, "finish", finish)
    worker.drain_outbox()
    assert get(ctx, batch["batch_id"])["counts"]["unknown"] == 1 and len(ctx.sent) == 1


def test_queue_unavailable_keeps_durable_outbox(emails, monkeypatch):
    ctx = emails; batch = generate(ctx, create(ctx))
    from src.workers.celery_app import celery_app
    def fail(*args, **kwargs): raise RuntimeError("SECRET redis")
    monkeypatch.setattr(celery_app, "send_task", fail)
    monkeypatch.setattr(inv, "publish_batch", ctx.publish)
    response = dispatch(ctx, batch)
    assert response.status_code == 202 and "SECRET" not in response.text
    assert response.json()["dispatch_error"] == "QUEUE_UNAVAILABLE"
    worker.drain_outbox()
    assert get(ctx, batch["batch_id"])["counts"]["success"] == 1


def test_revoked_approver_prevents_queued_sends(emails):
    from src.db.models import AppUser
    ctx = emails; batch = generate(ctx, create(ctx)); dispatch(ctx, batch)
    with ctx.api.db() as db:
        db.get(AppUser, ctx.api.users["admin"]).is_active = False; db.commit()
    worker.process_batch(batch["batch_id"])
    assert not ctx.sent
    with ctx.api.db() as db:
        assert db.scalar(select(InvitationDelivery)).error_code == "APPROVAL_REVOKED"


def test_permissions_validation_and_legacy_history(emails):
    ctx = emails; batch = create(ctx); draft = batch["drafts"][0]
    for path, method, body in [("/api/emails/history", "GET", None), (f'/api/emails/batches/{batch["batch_id"]}', "GET", None),
        (f'/api/emails/drafts/{draft["draft_id"]}/generate', "POST", {"expected_revision": 1})]:
        args = {"json": body} if body else {}
        assert ctx.api.client.request(method, path, **args).status_code == 401
        assert ctx.api.client.request(method, path, headers=ctx.api.headers("alice"), **args).status_code == 403
    assert dispatch(ctx, batch, confirmed=False).status_code == 422
    bad = ctx.api.client.post(f'/api/emails/drafts/{draft["draft_id"]}', headers=ctx.api.headers("admin"), json={"expected_revision": 1, "subject": "Injected\r\nBcc: secret", "body": "body"})
    assert bad.status_code == 422
    assert dispatch(ctx, batch).json()["error"]["code"] == "DRAFT_NOT_READY"
    with ctx.api.db() as db:
        db.add(SentEmail(candidate_id=ctx.ids[0], recipient_email="a@example.test", subject="Legacy", body="Old body", status="failed", error_message="SECRET stacktrace")); db.commit()
    response = ctx.api.client.get("/api/emails/history?q=Legacy&status=failed", headers=ctx.api.headers("admin"))
    assert response.status_code == 200 and "SECRET" not in response.text
    assert response.json()["total"] == 1
    assert ctx.api.client.get("/api/emails/history?date_from=2026-10-22&date_to=2026-10-01", headers=ctx.api.headers("admin")).status_code == 422
    assert ctx.api.client.get(f'/api/emails/batches/{uuid4()}', headers=ctx.api.headers("admin")).status_code == 404
    assert not ctx.sent


def test_two_worker_tasks_claim_only_one_actual_send(emails, monkeypatch):
    from threading import Event
    ctx = emails; batch = generate(ctx, create(ctx)); dispatch(ctx, batch)
    started, release = Event(), Event()
    class Gmail:
        def __init__(self, **kwargs): pass
        def send_message(self, **payload):
            ctx.sent.append(payload); started.set(); assert release.wait(5); return "gmail-once"
    monkeypatch.setattr(worker, "GmailClient", Gmail)
    with ThreadPoolExecutor() as executor:
        first = executor.submit(worker.process_batch, batch["batch_id"])
        try:
            assert started.wait(5)
            second = executor.submit(worker.process_batch, batch["batch_id"])
            second.result(timeout=5)
        finally: release.set()
        first.result(timeout=5)
    assert len(ctx.sent) == 1
    assert get(ctx, batch["batch_id"])["counts"]["success"] == 1


def test_migration_0013_upgrade_and_downgrade_sqlite(tmp_path):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    from src.db.models import Base
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    # Build an equivalent 0012 legacy schema without the new FK/column/tables.
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE app_users (user_id CHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE candidates (candidate_id CHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE sent_emails (id INTEGER PRIMARY KEY, body TEXT)"))
        connection.execute(text("INSERT INTO sent_emails(id, body) VALUES (1, 'legacy body')"))
        spec = importlib.util.spec_from_file_location("invitation_migration", "alembic/versions/add_invitation_outbox.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "invitation_deliveries" in inspect(connection).get_table_names()
            assert connection.execute(text("SELECT body, delivery_id FROM sent_emails WHERE id=1")).one() == ("legacy body", None)
            module.downgrade()
            assert "invitation_deliveries" not in inspect(connection).get_table_names()
            assert connection.execute(text("SELECT body FROM sent_emails WHERE id=1")).scalar_one() == "legacy body"
    engine.dispose()
