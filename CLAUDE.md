# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

CV RAG AI is a recruiting assistant: a Python backend (FastAPI + Celery + LangGraph agent on Gemini) and a Next.js frontend that acts as a BFF. Docs and the UI are in Vietnamese.

## Commands

Backend (repo root, Python 3.12, `.venv`):

```bash
source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
alembic upgrade head                                   # MySQL migrations
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1   # API, docs at /docs
celery -A src.workers.celery_app worker --loglevel=info
celery -A src.workers.celery_app beat --loglevel=info  # scheduled Gmail polling
streamlit run app.py                                   # legacy demo UI
python scripts/init_qdrant_collection.py               # one-time: create cv_chunks collection
python scripts/manage_users.py                         # create login accounts
```

Tests (CI runs `python -m pytest -q --cov=src`, `PYTHONPATH` = repo root; `tests/all test/` is excluded):

```bash
python -m pytest tests/api/test_chat.py::test_name -q
```

Frontend (in `frontend/`, Node >= 20.9, needs `.env.local` with `API_INTERNAL_URL=http://127.0.0.1:8000`):

```bash
npm ci
npm run dev
npm run format:check && npm run lint && npm run typecheck && npm run build   # same as CI
npm run test:e2e                                       # Playwright
```

Full stack: `docker compose` (services mysql, redis, qdrant, minio, api, worker, beat, frontend, proxy; profiles `demo`, `scheduler`). See `docs/deployment/demo.md`.

## Architecture

- **Entry points**: `main.py` → `src/api/app.py:create_app()` registers routers in `src/api/routes/`. Routes are thin; business logic lives in per-domain service modules (`src/chat/service.py`, `src/candidates/service.py`, `src/interview/`, `src/notification/`, `src/management/`, `src/ops/`). `src/interfaces/` holds older facade functions used by Streamlit/scripts.
- **Ingestion** (`src/ingestion/`): Gmail intake (`email_intake/`) or `interfaces/ingestion_interface.py` validates filename (`CV_FILENAME_PATTERN`) and dedupes, writes `ingestion_jobs`, then dispatches Celery task `process_cv_job` → `ingestion/pipeline.py`: MinIO load → PyMuPDF parse (Gemini multimodal OCR fallback) → classify → structured extraction → MySQL `candidates` → section chunks → Gemini embeddings (768d) → Qdrant `cv_chunks`. Permanent errors → `rejected`; transient → exponential retry then `dlq`.
- **Agent** (`src/agent/`): LangGraph agent with tools in `agent/tools/`; `router.ask()` is the entry. State is checkpointed (`src/chat/checkpoints.py`) — run only one process writing chat checkpoints (don't run Streamlit alongside the API).
- **Human-in-the-loop**: `find_top_candidates_for_jd` calls LangGraph `interrupt()`; the API returns `confirmation_required` and resumes on confirm. Ranking must never run before resume (`tests/test_double_opt_in.py`). The agent only *drafts* emails; real sending goes through a separate confirmed flow / Celery `send_bulk_emails`, logged to `sent_emails`.
- **Retrieval** (`src/retrieval/`): SQL hard filter → hybrid (BM25 + Qdrant) → rerank → rubric scoring (`src/evaluation/`). `skill_normalizer.py` expands synonyms at query time only.
- **Access control**: department scoping is enforced at the DB layer via `contextvars` in `retrieval/access_scope.py`, never as an LLM-chosen parameter. Keep it that way for any new query path.
- **Gemini keys**: `src/llm/key_manager.py` fails over across `GOOGLE_API_KEY`, `GOOGLE_API_KEY_2`, ... on 429, with the active index shared via Redis across workers. All Gemini calls should go through it. Prompts are managed via `src/llm/prompt_store.py` (LangSmith).
- **Frontend**: Next.js App Router (`frontend/src/app`), feature modules in `src/features/`, contracts (zod) in `src/lib/contracts.ts`. The browser never calls FastAPI directly: `app/api/backend` proxies via `lib/server/backend.ts`, with the bearer token in an HttpOnly cookie; authorization is always checked by FastAPI.
- **Next.js version is newer than training data** (Next 16, React 19): per `frontend/AGENTS.md`, read `frontend/node_modules/next/dist/docs/` before writing Next code and heed deprecations.

API contracts and per-feature docs: `docs/api/` (`contract.md`, `setup.md`, etc.).
