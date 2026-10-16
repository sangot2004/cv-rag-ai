"""ASGI entrypoint: uvicorn main:app --host 127.0.0.1 --port 8000."""
from src.api.app import create_app

app = create_app()
