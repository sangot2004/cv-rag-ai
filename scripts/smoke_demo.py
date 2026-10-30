"""Check real HTTPS/BFF login, read permissions and logout without AI or email."""
import argparse
from getpass import getpass
import os
import ssl
from urllib.parse import urlsplit

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="Exact HTTPS frontend origin, e.g. https://localhost")
    parser.add_argument("--username", required=True)
    parser.add_argument("--ca-cert", help="Caddy local CA certificate; omit for a publicly trusted domain")
    parser.add_argument("--password-env", help="Optional name of an environment variable containing the password")
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    url = urlsplit(origin)
    if url.scheme != "https" or url.username or url.password or url.path or url.query or url.fragment:
        parser.error("Use an HTTPS origin without credentials or a path.")
    password = os.environ.get(args.password_env, "") if args.password_env else getpass("Mật khẩu demo: ")
    if not password:
        parser.error("Password is empty.")
    context = ssl.create_default_context(cafile=args.ca_cert)
    with httpx.Client(base_url=origin, verify=context, timeout=20, follow_redirects=False) as client:
        step = "anonymous access"
        try:
            assert client.get("/api/session/me").status_code == 401
            step = "login"
            response = client.post("/api/session/login", headers={"Origin": origin}, json={"username": args.username, "password": password})
            assert response.status_code == 200
            assert "access_token" not in response.json()
            cookie = response.headers.get("set-cookie", "").lower()
            assert "__host-cv_session=" in cookie and "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
            print("PASS HTTPS login and Secure/HttpOnly/SameSite cookie")
            step = "identity"
            identity = client.get("/api/session/me")
            assert identity.status_code == 200
            # Login and /me expose the user, not the backend bearer token.
            user = identity.json()
            role = user.get("role") or user.get("user", {}).get("role")
            assert role in {"admin", "tester"}
            step = "private reads"
            for path in ("/api/backend/conversations", "/api/backend/candidates?page_size=1"):
                response = client.get(path)
                assert response.status_code == 200
                assert "no-store" in response.headers.get("cache-control", "")
            print("PASS authenticated candidate and conversation reads")
            step = "role restrictions"
            for path in ("/api/backend/admin/users", "/api/backend/ingestion/jobs", "/api/backend/emails/history", "/api/backend/ops/dashboard?days=7"):
                assert client.get(path).status_code == (200 if role == "admin" else 403)
            print("PASS " + role + " API permissions")
            step = "origin enforcement"
            assert client.post("/api/backend/conversations", json={}).status_code == 403
            print("PASS mutation origin guard")
            step = "logout"
            assert client.post("/api/session/logout", headers={"Origin": origin}, json={}).status_code == 204
            assert client.get("/api/session/me").status_code == 401
            print("PASS logout revokes the session")
        except (AssertionError, ValueError, httpx.HTTPError) as error:
            raise SystemExit("FAIL " + step + " (" + type(error).__name__ + "); inspect service logs locally.") from None


if __name__ == "__main__":
    main()
