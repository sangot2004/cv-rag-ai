from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from src.api.dependencies import Token
from src.api.execution import execute
from src.api.schemas.chat import AttachmentExtractResponse
from src.api.schemas.common import ERROR_RESPONSES
from src.chat import attachments
from src.chat.errors import AttachmentError

router = APIRouter(prefix="/api/attachments", tags=["chat"], responses=ERROR_RESPONSES)


@router.post("/extract", response_model=AttachmentExtractResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file"], "properties": {
            "file": {"type": "string", "format": "binary"}}}}}}})
async def extract(request: Request, token: Token, response: Response):
    if not request.headers.get("content-type", "").startswith("multipart/form-data;"):
        raise AttachmentError("MULTIPART_REQUIRED", "Cần gửi file bằng multipart/form-data.", 415)
    async with request.form(max_files=1, max_fields=1) as form:
        file = form.get("file")
        if not isinstance(file, UploadFile) or set(form.keys()) != {"file"}:
            raise AttachmentError("FILE_REQUIRED", "Cần đính kèm một file.")
        data = await file.read(attachments.MAX_ATTACHMENT_BYTES + 1)
        if len(data) > attachments.MAX_ATTACHMENT_BYTES:
            raise AttachmentError(
                "ATTACHMENT_TOO_LARGE",
                "File vượt quá dung lượng cho phép (tối đa 15MB).",
                413,
            )
        filename = file.filename or "attachment"
        text = await run_in_threadpool(execute, token, response, attachments.extract_text, data, filename)
        return {"filename": filename, "text": text}
