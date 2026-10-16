from typing import Annotated
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.errors import AuthenticationRequired

bearer = HTTPBearer(auto_error=False)


def bearer_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    # Extract only: auth_scope must open inside the route's own worker thread.
    if credentials is None:
        raise AuthenticationRequired("Bạn cần đăng nhập.")
    return credentials.credentials


Token = Annotated[str, Depends(bearer_token)]
