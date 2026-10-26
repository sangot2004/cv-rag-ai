from src.workers.celery_app import celery_app


@celery_app.task(name="src.workers.tasks_ops.experiment")
def experiment(identifier):
    from src.ops.workflow import execute_job
    execute_job(identifier)
