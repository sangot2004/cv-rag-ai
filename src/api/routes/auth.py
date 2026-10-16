from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from src.api.dependencies import Token
from src.api.schemas.auth import LoginRequest, TokenResponse, UserResponse
from src.api.schemas.common import ERROR_RESPONSES
from src.auth import service

router = APIRouter(prefix="/api/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    token = service.login(body.username, body.password.get_secret_value())
    try:
        with service.auth_scope(token) as user:
            expires_at = service.session_expiry(token)
            return TokenResponse(access_token=token, expires_at=expires_at,
                                 expires_in=max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds())),
                                 user=UserResponse(**asdict(user)))
    except Exception:
        service.logout(token)
        raise


@router.get("/me", response_model=UserResponse)
def me(token: Token):
    with service.auth_scope(token) as user:
        return asdict(user)


@router.post("/logout", status_code=204, response_class=Response)
def logout(token: Token):
    with service.auth_scope(token):
        service.logout(token)
    return Response(status_code=204)
