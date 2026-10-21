import uuid
from starlette.requests import Request
from src.api.exception_handlers import error_response


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = False

        async def send_with_id(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            upload = scope.get("path") == "/api/ingestion/uploads"
            received = 0

            async def bounded_receive():
                nonlocal received
                message = await receive()
                if upload and message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > 50 * 1024 * 1024 + 65536:
                        from src.management.errors import ManagementError
                        raise ManagementError("FILE_TOO_LARGE", "File vượt quá dung lượng cho phép.", 413)
                return message

            await self.app(scope, bounded_receive, send_with_id)
        except Exception as exc:
            if started:
                raise
            response = await error_response(Request(scope), exc)
            await response(scope, receive, send_with_id)
