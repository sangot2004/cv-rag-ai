from datetime import datetime, timedelta, timezone

from src.auth import service as auth
from src.db.models import AppUser, AuthSession
from .conftest import PASSWORD


def test_health_docs_cors_and_validation(api):
    client = api.client
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    preflight = client.options("/api/auth/me", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization, Content-Type"})
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": "https://evil.test"}).headers
    denied = client.get("/api/auth/me", headers={"Origin": "http://localhost:3000"})
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"
    assert denied.headers["x-request-id"] == denied.json()["error"]["request_id"]
    assert denied.headers["access-control-allow-origin"] == "http://localhost:3000"
    invalid = client.post("/api/auth/login", json={"username": "a", "password": "secret", "role": "admin"})
    assert invalid.status_code == 422
    assert "secret" not in invalid.text
    assert "password" not in invalid.text


def test_login_me_expiry_logout(api):
    client = api.client
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    result = client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
    assert result.status_code == 200
    payload = result.json()
    assert 43190 <= payload["expires_in"] <= 43200
    assert payload["expires_at"].endswith("Z")
    assert payload["user"]["role"] == "tester"
    headers = {"Authorization": "Bearer " + payload["access_token"]}
    assert client.get("/api/auth/me", headers=headers).json()["username"] == "alice"
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert auth._token.get() is None


def test_expired_disabled_and_invalid_role(api):
    with api.db() as db:
        db.get(AuthSession, auth._digest(api.tokens["alice"])).expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.get(AppUser, api.users["bobby"]).is_active = False
        db.get(AppUser, api.users["carol"]).role = "invented"
        db.commit()
    for name in ("alice", "bobby", "carol"):
        assert api.client.get("/api/auth/me", headers=api.headers(name)).status_code == 401
    with api.db() as db:
        before = db.query(AuthSession).filter_by(user_id=api.users["carol"]).count()
    result = api.client.post("/api/auth/login", json={"username": "carol", "password": PASSWORD})
    assert result.status_code == 401
    with api.db() as db:
        assert db.query(AuthSession).filter_by(user_id=api.users["carol"]).count() == before


def test_tester_missing_department_token_revoked(api):
    with api.db() as db:
        db.get(AppUser, api.users["carol"]).department_id = None
        db.query(AuthSession).filter_by(user_id=api.users["carol"]).delete()
        db.commit()
    assert api.client.post("/api/auth/login", json={"username": "carol", "password": PASSWORD}).status_code == 401
    with api.db() as db:
        assert db.query(AuthSession).filter_by(user_id=api.users["carol"]).count() == 0
