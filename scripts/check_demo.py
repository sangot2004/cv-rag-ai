"""Read-only demo checks. Never call a model, refresh Gmail, or send mail."""
import argparse
import json
import logging
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", action="store_true", help="Require locally prepared Gmail OAuth files")
    parser.add_argument("--worker", action="store_true", help="Require a Celery worker to answer ping")
    parser.add_argument("--api-url", help="Optional API origin for GET /health")
    parser.add_argument("--frontend-url", help="Optional frontend origin for GET /login")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    from src.config.settings import get_settings
    settings = get_settings()
    failed = []

    def check(name, fn):
        try:
            assert fn(), "NotReady"
            print("PASS " + name)
        except Exception as error:
            # Provider errors may contain credentials/URLs; print only their type.
            failed.append(name)
            print("FAIL " + name + " (" + type(error).__name__ + ")")

    def database():
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.MYSQL_CONN, connect_args={"connect_timeout": 3})
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                actual = set(MigrationContext.configure(connection).get_current_heads())
            expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
            return actual == expected
        finally:
            engine.dispose()

    def redis_ready():
        from redis import Redis
        with Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3) as client:
            return client.ping()

    def vectors():
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.QDRANT_URL, timeout=3)
        try:
            params = client.get_collection(settings.QDRANT_COLLECTION).config.params.vectors
            return getattr(params, "size", None) == settings.EMBEDDING_DIM
        finally:
            client.close()

    def storage():
        from minio import Minio
        import urllib3
        http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=3, read=3), retries=False)
        try:
            return Minio(settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE, http_client=http).bucket_exists(settings.MINIO_BUCKET)
        finally:
            http.clear()

    def checkpoints():
        from src.chat.checkpoints import history_path
        path = history_path()
        return os.access(path if path.exists() else path.parent, os.W_OK)

    def configured(value):
        return bool(value and not value.startswith(("your_", "replace_")))

    check("MySQL connection and Alembic revision", database)
    check("Redis", redis_ready)
    check("Qdrant collection and embedding dimension", vectors)
    check("MinIO bucket", storage)
    check("Checkpoint path is writable", checkpoints)
    check("Gemini key configured (not remotely validated)", lambda: configured(settings.GOOGLE_API_KEY))
    check("LangSmith key configured (not remotely validated)", lambda: configured(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")))
    if args.email:
        def gmail_files():
            client = json.loads(Path(settings.GMAIL_CREDENTIALS_PATH).read_text())
            token = json.loads(Path(settings.GMAIL_TOKEN_PATH).read_text())
            scopes = set(token.get("scopes", []))
            return bool(client.get("installed") and token.get("refresh_token") and {
                "https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"} <= scopes)
        check("Gmail files and declared scopes (not remotely validated)", gmail_files)
    else:
        print("SKIP Gmail OAuth files; use --email for an email demo")
    if args.worker:
        def worker_ready():
            from src.workers.celery_app import celery_app
            return bool(celery_app.control.inspect(timeout=3).ping())
        check("Celery worker responds", worker_ready)
    for name, origin, path in [("API health", args.api_url, "/health"), ("Frontend login", args.frontend_url, "/login")]:
        if origin:
            def reachable(origin=origin, path=path):
                import httpx
                return httpx.get(origin.rstrip("/") + path, timeout=5, follow_redirects=False).status_code == 200
            check(name, reachable)
    print(f"\n{len(failed)} failed check(s). External model/prompt/OAuth access still needs a manual acceptance test.")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
