import logging
import sqlite3

import httpx
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from langsmith.utils import LangSmithError
from google.genai.errors import APIError
from redis.exceptions import RedisError

from src.auth.errors import AccessDenied, AuthenticationRequired, ConversationNotFound
from src.chat.errors import ChatConflict, CleanupPending, DependencyUnavailable, MessageNotFound
from src.llm.key_manager import is_quota_error

logger = logging.getLogger(__name__)


async def error_response(request, exc):
    status, code, message = 500, "INTERNAL_ERROR", "Đã xảy ra lỗi nội bộ."
    if isinstance(exc, AuthenticationRequired):
        status, code, message = 401, "AUTHENTICATION_REQUIRED", "Thông tin đăng nhập hoặc phiên không hợp lệ."
    elif isinstance(exc, ConversationNotFound):
        status, code, message = 404, "CONVERSATION_NOT_FOUND", "Không tìm thấy hội thoại hoặc bạn không có quyền truy cập."
    elif isinstance(exc, AccessDenied):
        status, code, message = 403, "FORBIDDEN", "Bạn không có quyền dùng chức năng này."
    elif isinstance(exc, ChatConflict):
        status, code, message = 409, exc.code, str(exc)
    elif isinstance(exc, CleanupPending):
        status, code, message = 503, "CONVERSATION_CLEANUP_PENDING", "Hội thoại đã ẩn. Hãy thử xóa lại để hoàn tất dọn dữ liệu."
    elif isinstance(exc, MessageNotFound):
        status, code, message = 404, "MESSAGE_NOT_FOUND", "Không tìm thấy câu trả lời trong hội thoại."
    elif isinstance(exc, RequestValidationError):
        # Never echo input or Pydantic error context (may contain a password).
        status, code, message = 422, "VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ. Hãy kiểm tra schema tại /docs."
    elif isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        status, code, message = 504, "DEPENDENCY_TIMEOUT", "Dịch vụ phụ thuộc phản hồi quá thời gian chờ."
    elif isinstance(exc, (SQLAlchemyError, sqlite3.Error, httpx.RequestError, LangSmithError, APIError, RedisError, DependencyUnavailable)) or is_quota_error(exc):
        status, code, message = 503, "DEPENDENCY_UNAVAILABLE", "Dịch vụ phụ thuộc tạm thời không khả dụng."
    elif isinstance(exc, HTTPException):
        status, code, message = exc.status_code, "HTTP_ERROR", "Yêu cầu HTTP không hợp lệ."
    request_id = request.state.request_id
    # Type and correlation only: provider exceptions can include keys/DSNs/CV text.
    logger.log(logging.ERROR if status >= 500 else logging.INFO,
               "request_id=%s status=%s code=%s exception_type=%s",
               request_id, status, code, type(exc).__name__)
    headers = {"X-Request-ID": request_id}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"error": {"code": code, "message": message, "request_id": request_id}},
                        status_code=status, headers=headers)
