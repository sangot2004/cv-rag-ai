from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from src.api.dependencies import Token
from src.api.execution import execute
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.ingestion import JobFilters, JobPage, JobView, RetryJob, UploadCapabilities
from src.auth.service import auth_scope, require_admin
from src.ingestion import jobs
from src.management.errors import ManagementError

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"], responses=ERROR_RESPONSES)


@router.get("/capabilities", response_model=UploadCapabilities)
def capabilities(token: Token, response: Response):
    return execute(token, response, jobs.capabilities)


@router.get("/jobs", response_model=JobPage)
def listing(token: Token, response: Response, filters: Annotated[JobFilters, Query()]):
    return execute(token, response, jobs.listing, **filters.model_dump())


@router.get("/jobs/{job_id}", response_model=JobView)
def detail(job_id: UUID, token: Token, response: Response):
    return execute(token, response, jobs.detail, str(job_id))


@router.post("/jobs/{job_id}/retry", response_model=JobView, status_code=202)
def retry(job_id: UUID, body: RetryJob, token: Token, response: Response):
    return execute(token, response, jobs.retry, str(job_id))


def authorize(token):
    with auth_scope(token):
        require_admin()


@router.post("/uploads", response_model=JobView, status_code=202, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file", "posting_id"], "properties": {
            "file": {"type": "string", "format": "binary"}, "posting_id": {"type": "string", "format": "uuid"}}}}}}})
async def upload(request: Request, token: Token, response: Response):
    # Authorize before reading/spooling the multipart body. Repeat in the worker
    # thread after reading in case the account was revoked during upload.
    await run_in_threadpool(authorize, token)
    if not request.headers.get("content-type", "").startswith("multipart/form-data;"):
        raise ManagementError("MULTIPART_REQUIRED", "Cần gửi file bằng multipart/form-data.", 415)
    async with request.form(max_files=1, max_fields=1) as form:
        file = form.get("file")
        try:
            posting = str(UUID(str(form.get("posting_id"))))
        except ValueError:
            raise ManagementError("POSTING_REQUIRED", "Hãy chọn vị trí tuyển dụng hợp lệ.", 422) from None
        if not isinstance(file, UploadFile) or set(form.keys()) != {"file", "posting_id"}:
            raise ManagementError("FILE_REQUIRED", "Cần một file PDF và vị trí tuyển dụng.", 422)
        data = await file.read(min(jobs.settings.CV_MAX_FILE_SIZE_BYTES, jobs.HARD_MAX_BYTES) + 1)
        return await run_in_threadpool(execute, token, response, jobs.upload, data, file.filename, posting)
