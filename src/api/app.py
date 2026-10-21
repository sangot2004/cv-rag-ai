import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from src.api.exception_handlers import error_response
from src.api.middleware import RequestIdMiddleware
from src.api.routes import auth, candidates, chat, conversations, health, interviews, emails, management, ingestion
from src.chat.checkpoints import close_checkpointer


@asynccontextmanager
async def lifespan(app):
    yield
    close_checkpointer()


def create_app() -> FastAPI:
    app = FastAPI(title="CV RAG AI API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, error_response)
    app.add_exception_handler(HTTPException, error_response)
    app.add_middleware(RequestIdMiddleware)
    origins = [origin.strip() for origin in os.getenv(
        "API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("API_CORS_ORIGINS must contain explicit origins")
    # CORS wraps our error middleware so errors also reach allowed browser clients.
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"],
                       expose_headers=["X-Request-ID"])
    for router in (health.router, auth.router, conversations.router, chat.router, candidates.router, interviews.router, emails.router, management.router, ingestion.router):
        app.include_router(router)
    return app
