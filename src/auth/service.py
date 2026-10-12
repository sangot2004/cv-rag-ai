import hashlib
import hmac
import secrets

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps

from src.db.models import AppUser, AuthSession, Department
from src.db.session import SessionLocal

_token = ContextVar("token", default=None)


def _utcnow_for_db():
    """Return UTC time without tzinfo to match SQL DATETIME values."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AccessDenied(PermissionError):
    pass


@dataclass(frozen=True)
class Identity:
    user_id: str
    username: str
    role: str
    department_id: str | None


def hash_password(password):
    if not 12 <= len(password) <= 256:
        raise ValueError("Mật khẩu cần từ 12 đến 256 ký tự.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    if len(password) > 256:
        return False
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_urlsafe(24))


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def login(username, password):
    now = _utcnow_for_db()
    with SessionLocal() as db:
        user = db.query(AppUser).filter_by(username=username.strip().lower()).with_for_update().first()

        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise AccessDenied("Thông tin đăng nhập không hợp lệ hoặc tài khoản tạm khóa.")

        if not user.is_active or (user.locked_until and user.locked_until > now):
            raise AccessDenied("Thông tin đăng nhập không hợp lệ hoặc tài khoản tạm khóa.")

        if not verify_password(password, user.password_hash):
            user.failed_attempts += 1
            if user.failed_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_attempts = 0
            db.commit()
            raise AccessDenied("Thông tin đăng nhập không hợp lệ hoặc tài khoản tạm khóa.")

        user.failed_attempts = 0
        user.locked_until = None
        token = secrets.token_urlsafe(32)

        db.query(AuthSession).filter(AuthSession.expires_at <= now).delete()
        db.add(AuthSession(token_hash=_digest(token), user_id=user.user_id,
                           expires_at=now + timedelta(hours=12)))

        db.commit()
        return token


def logout(token):
    if token:
        with SessionLocal() as db:
            db.query(AuthSession).filter_by(token_hash=_digest(token)).delete()
            db.commit()


def require_user():
    token = _token.get()
    if not token:
        raise AccessDenied("Bạn cần đăng nhập.")

    with SessionLocal() as db:
        session = db.get(AuthSession, _digest(token))
        if session is None or session.expires_at <= _utcnow_for_db():
            raise AccessDenied("Phiên đăng nhập đã hết hạn.")
        user = db.get(AppUser, session.user_id)
        if user is None or not user.is_active or user.role not in ("admin", "tester"):
            raise AccessDenied("Tài khoản không còn quyền truy cập.")
        if user.role == "tester" and not user.department_id:
            raise AccessDenied("Tester chưa được gán phòng ban.")
        return Identity(user.user_id, user.username, user.role, user.department_id)


@contextmanager
def auth_scope(token):
    marker = _token.set(token)
    try:
        yield require_user()
    finally:
        _token.reset(marker)


def require_admin():
    user = require_user()
    if user.role != "admin":
        raise AccessDenied("Chức năng này chỉ dành cho admin.")
    return user


def admin_only(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        require_admin()
        return fn(*args, **kwargs)
    return wrapped


def resolve_department(requested=None):
    user = require_user()
    if user.role == "admin":
        return requested

    if requested is not None and requested != user.department_id:
        raise AccessDenied("Không được đổi phạm vi phòng ban.")

    return user.department_id


def _create_user(username, password, role, department_id=None):
    username = username.strip().lower()
    if not 3 <= len(username) <= 100 or role not in ("admin", "tester"):
        raise ValueError("Tên tài khoản 3–100 ký tự; quyền phải là admin hoặc tester.")

    if role == "tester" and not department_id:
        raise ValueError("Tester phải được gán một phòng ban.")

    password_hash = hash_password(password)

    with SessionLocal() as db:
        if department_id and db.get(Department, department_id) is None:
            raise ValueError("Phòng ban không tồn tại.")

        if db.query(AppUser).filter_by(username=username).first():
            raise ValueError("Tên tài khoản đã tồn tại.")

        user = AppUser(username=username, password_hash=password_hash, role=role,
                       department_id=department_id, is_active=True)

        db.add(user)
        db.flush()
        identifier = user.user_id
        db.commit()

        return identifier


@admin_only
def create_user(username, password, role="tester", department_id=None):
    return _create_user(username, password, role, department_id)


@admin_only
def set_user_active(user_id, active):
    admin = require_admin()
    if user_id == admin.user_id:
        raise ValueError("Không thể đổi trạng thái chính tài khoản đang đăng nhập.")

    if type(active) is not bool:
        raise ValueError("Trạng thái tài khoản phải là boolean.")

    with SessionLocal() as db:
        user = db.get(AppUser, user_id)
        if user is None:
            raise ValueError("Tài khoản không tồn tại.")

        user.is_active = active

        db.query(AuthSession).filter_by(user_id=user_id).delete()
        db.commit()
