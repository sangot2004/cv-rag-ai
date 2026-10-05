# Phase 1 + 2: AI usage and System Ops

## Setup

```bash
pip install -r requirements.txt
alembic upgrade head
streamlit run app.py
```

Keep your existing .env. Add OPS\_\* settings from .env.example. Restart Streamlit and Celery workers to load the new code/settings. Existing Gmail polling remains every two minutes.

## Pricing

OPS_MODEL_PRICES_JSON maps exact model names to input/output/cached_input rates in USD per million tokens. Default {} deliberately means unknown pricing, not free usage. Example ONLY (fictional model/rates):

```dotenv
OPS_MODEL_PRICES_JSON={"example-model":{"input":1.0,"output":2.0,"cached_input":0.25}}
OPS_PRICING_VERSION=your-price-table-date
```

Set rates from your provider's current price table and billing tier. Estimated cost is not an invoice. Output usage includes reasoning when the provider reports it that way; reasoning is stored separately but is not added twice. No historical recalculation: each row snapshots the estimate and pricing version. Missing provider usage is NULL.

## Coverage

LangChain callbacks record model calls in classification, extraction, OCR, JD extraction/evaluation, chat agent, email drafts, interview questions. Direct google.genai embeddings are measured separately. operation_id groups child calls; job_id/candidate_id/thread_id link business entities where applicable. Every callback-observed failed attempt is recorded. Hidden SDK retries may not be individually visible; errors may not expose billable token usage.

Logs persist metadata only, not prompts, CV contents or API keys. Writes are best effort: a DB logging error is logged and does not fail the business operation. No durable telemetry queue in this MVP. Call latency excludes queue waiting, parsing, reranking and human confirmation time. It is not complete end-to-end business latency.

System Ops shows time/module/model filters, tokens, estimated priced costs, missing-data coverage, error rate, median/p95 call latency, token trends, scatter plot, per-job observed costs and rule alerts. Per-CV costs within selected filters/time range may be partial. DLQ count is global. Demo dashboard inherits the existing application's lack of login; add backend-admin authorization before multi-user deployment. For large log volumes use server-side aggregation/pagination; MVP loads selected date range.

## Verification

```bash
pytest tests/test_ops.py -v
pytest tests/ -v
```

Integration check on your running services: process a PDF, ask a question, draft an email without sending, generate interview questions; verify usage modules in System Ops. Disable with OPS_ENABLED=false. No Phase 3 caching/model routing or Phase 4 config agent is implemented.

## Validation in delivery environment

19 tests passed (6 Ops + 13 existing key-manager tests); Python syntax checks passed; full migration chain generated MySQL SQL offline. No live provider/Streamlit rendering or full existing test-suite execution was performed.
