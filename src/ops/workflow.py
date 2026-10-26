"""Admin workflow and durable experiment dispatch; no session secrets in Celery."""
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, select, update
from src.db.models import Base, AppUser
from src.db import session as database
from src.auth.service import admin_only, require_admin
from src.management.errors import ManagementError
from src.ops.locking import ops_lock as named_lock
from src.ops import optimization as opt


class ExperimentJob(Base):
    __tablename__ = "ops_experiment_jobs"
    id = Column(String(36), primary_key=True)
    proposal_id = Column(String(36), nullable=False, index=True)
    requested_by = Column(String(36), nullable=False)
    dataset = Column(String(200), nullable=False)
    status = Column(String(24), nullable=False)
    error_code = Column(String(64))
    report_json = Column(Text)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def conflict(message):
    raise ManagementError("OPTIMIZATION_CONFLICT", message)


@admin_only
def overview():
    with database.SessionLocal() as db:
        pointer = db.get(opt.OptimizationPointer, 1)
        rows = db.scalars(select(opt.OptimizationConfig).order_by(opt.OptimizationConfig.created_at.desc()).limit(100)).all()
        jobs = db.scalars(select(ExperimentJob).order_by(ExperimentJob.created_at.desc()).limit(100)).all()
        return {"active_id": pointer.config_id if pointer else None, "active": opt.active_config(),
                "proposals": [{"id": r.id, "settings": json.loads(r.settings_json), "status": r.status,
                               "report": json.loads(r.report_json) if r.report_json else None} for r in rows],
                "jobs": [{"id": r.id, "proposal_id": r.proposal_id, "dataset": r.dataset,
                          "status": r.status, "error_code": r.error_code} for r in jobs]}


@admin_only
def create(settings):
    return {"id": opt.propose(settings)}


@admin_only
def enqueue(identifier, dataset):
    user = require_admin()
    with named_lock("ops:" + identifier) as acquired:
        if not acquired:
            conflict("Experiment đang chạy.")
        with database.SessionLocal() as db:
            row = db.get(opt.OptimizationConfig, identifier)
            if not row or row.status == "approved":
                conflict("Đề xuất không tồn tại hoặc đã được duyệt.")
            pending = db.scalar(select(ExperimentJob).where(ExperimentJob.proposal_id == identifier,
                ExperimentJob.status.in_(["queued", "running"])))
            if pending:
                conflict("Đề xuất đã có experiment đang chờ hoặc đang chạy.")
            if json.loads(row.settings_json)["retrieval_multiplier"] != opt.active_config()["retrieval_multiplier"]:
                conflict("Experiment hiện chỉ hỗ trợ extraction; hãy giữ cấu hình retrieval hiện tại.")
            identifier_job = str(uuid.uuid4())
            row.report_json = None
            db.add(ExperimentJob(id=identifier_job, proposal_id=identifier, dataset=dataset,
                requested_by=user.user_id, status="queued"))
            db.commit()
    dispatch(identifier_job)
    return {"id": identifier_job}


def dispatch(identifier):
    try:
        from src.workers.tasks_ops import experiment
        experiment.apply_async(args=[identifier], retry=False)
    except Exception:
        with database.SessionLocal() as db:
            db.execute(update(ExperimentJob).where(ExperimentJob.id == identifier,
                ExperimentJob.status == "queued").values(error_code="QUEUE_UNAVAILABLE"))
            db.commit()


@admin_only
def recover(identifier):
    with database.SessionLocal() as db:
        job = db.get(ExperimentJob, identifier)
        if not job:
            conflict("Không tìm thấy experiment.")
        proposal_id = job.proposal_id
    with named_lock("ops:" + proposal_id) as acquired:
        if not acquired:
            conflict("Worker đang chạy experiment này.")
        with database.SessionLocal() as db:
            job = db.get(ExperimentJob, identifier)
            if job.status == "running":
                job.status, job.error_code = "failed", "WORKER_INTERRUPTED"
                db.commit()
                return {"status": "failed"}
            if job.status != "queued":
                conflict("Chỉ khôi phục experiment đang chờ hoặc bị gián đoạn.")
        dispatch(identifier)
    return {"status": "queued"}


@admin_only
def activate(identifier, rollback=False):
    with named_lock("ops:" + str(identifier)) as acquired:
        if not acquired:
            conflict("Experiment đang chạy, hãy chờ hoàn tất.")
        with database.SessionLocal() as db:
            if db.scalar(select(ExperimentJob.id).where(ExperimentJob.proposal_id == identifier,
                    ExperimentJob.status.in_(["queued", "running"]))):
                conflict("Experiment chưa hoàn tất.")
        try:
            opt.rollback(identifier) if rollback else opt.approve(identifier)
        except ValueError:
            conflict("Chưa đủ điều kiện duyệt hoặc baseline đã thay đổi. Hãy chạy lại experiment.")
    return {"status": "ok"}


def execute_job(identifier):
    with database.SessionLocal() as db:
        job = db.get(ExperimentJob, identifier)
        if not job or job.status != "queued":
            return
        proposal_id = job.proposal_id
    with named_lock("ops:" + proposal_id) as acquired:
        if not acquired:
            return
        with database.SessionLocal() as db:
            job = db.get(ExperimentJob, identifier)
            if job.status != "queued":
                return
            user = db.get(AppUser, job.requested_by)
            if not user or not user.is_active or user.role != "admin":
                job.status, job.error_code = "failed", "REQUESTER_ACCESS_REVOKED"
                db.commit()
                return
            dataset = job.dataset
            job.status, job.error_code = "running", None
            db.commit()
        try:
            from src.ops.experiments import run_experiment
            # Internal runner: creator authorization was rechecked above; no bearer in broker.
            report = run_experiment.__wrapped__(proposal_id, dataset)
            status, error = "completed", None
        except Exception:
            report, status, error = None, "failed", "EXPERIMENT_FAILED"
        with database.SessionLocal() as db:
            job = db.get(ExperimentJob, identifier)
            job.status, job.error_code = status, error
            job.report_json = json.dumps(report) if report else None
            db.commit()
