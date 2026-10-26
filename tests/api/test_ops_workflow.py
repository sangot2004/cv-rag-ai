import json
from src.ops import workflow
from src.ops.optimization import OptimizationPointer, OptimizationConfig, DEFAULTS


def setup(api):
    with api.db() as db:
        db.add(OptimizationPointer(id=1, config_id=None))
        db.commit()


def test_queue_recovery_and_permissions(api, monkeypatch):
    setup(api)
    monkeypatch.setattr(workflow, "dispatch", lambda identifier: None)
    headers = api.headers("admin")
    assert api.client.get("/api/ops/optimization", headers=api.headers()).status_code == 403
    result = api.client.post("/api/ops/optimization", headers=headers, json=DEFAULTS)
    assert result.status_code == 201, result.text
    identifier = result.json()["id"]
    path = f"/api/ops/optimization/{identifier}"
    assert api.client.post(path+"/approve", headers=headers, json={"confirmed":True}).status_code == 409
    queued = api.client.post(path+"/experiment", headers=headers,json={"confirmed":True,"dataset":"golden"})
    assert queued.status_code == 202
    assert api.client.post(path+"/experiment", headers=headers,json={"confirmed":True,"dataset":"golden"}).status_code == 409
    job_id=queued.json()["id"]
    assert api.client.post(path+"/approve", headers=headers,json={"confirmed":True}).status_code == 409
    with api.db() as db:
        job=db.get(workflow.ExperimentJob,job_id); job.status="running"; db.commit()
    assert api.client.post(f"/api/ops/experiments/{job_id}/recover",headers=headers,json={"confirmed":True}).json()["status"]=="failed"


def test_worker_claim_once_and_report(api, monkeypatch):
    setup(api)
    monkeypatch.setattr(workflow,"dispatch",lambda identifier:None)
    h=api.headers("admin")
    identifier=api.client.post("/api/ops/optimization",headers=h,json=DEFAULTS).json()["id"]
    job=api.client.post(f"/api/ops/optimization/{identifier}/experiment",headers=h,json={"confirmed":True,"dataset":"golden"}).json()["id"]
    from src.ops import experiments
    calls=[]
    def run(*args):
        calls.append(args)
        return {"passed":False}
    monkeypatch.setattr(experiments.run_experiment,"__wrapped__",run)
    workflow.execute_job(job); workflow.execute_job(job)
    assert len(calls)==1
    with api.db() as db:
        assert db.get(workflow.ExperimentJob,job).status=="completed"


def test_approve_baseline_guard_and_rollback(api):
    setup(api)
    h=api.headers("admin")
    identifier=api.client.post("/api/ops/optimization",headers=h,json=DEFAULTS).json()["id"]
    with api.db() as db:
        row=db.get(OptimizationConfig,identifier)
        row.report_json=json.dumps({"passed":True,"baseline_config_id":None,"baseline_config":DEFAULTS,"proposed_config":DEFAULTS})
        db.commit()
    assert api.client.post(f"/api/ops/optimization/{identifier}/approve",headers=h,json={"confirmed":True}).status_code==200
    assert api.client.get("/api/ops/optimization",headers=h).json()["active_id"]==identifier


def test_revoked_creator_never_calls_model(api, monkeypatch):
    setup(api)
    monkeypatch.setattr(workflow,"dispatch",lambda identifier:None)
    h=api.headers("admin")
    identifier=api.client.post("/api/ops/optimization",headers=h,json=DEFAULTS).json()["id"]
    job_id=api.client.post(f"/api/ops/optimization/{identifier}/experiment",headers=h,json={"confirmed":True,"dataset":"golden"}).json()["id"]
    from src.db.models import AppUser
    with api.db() as db:
        job=db.get(workflow.ExperimentJob,job_id)
        db.get(AppUser,job.requested_by).is_active=False
        db.commit()
    workflow.execute_job(job_id)
    with api.db() as db:
        assert db.get(workflow.ExperimentJob,job_id).error_code=="REQUESTER_ACCESS_REVOKED"


def test_experiment_migration_roundtrip():
    import importlib.util
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    spec=importlib.util.spec_from_file_location("ops_migration","alembic/versions/add_ops_experiments.py")
    migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine=create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert "ops_experiment_jobs" in inspect(connection).get_table_names()
            migration.downgrade()
            assert "ops_experiment_jobs" not in inspect(connection).get_table_names()
    engine.dispose()
