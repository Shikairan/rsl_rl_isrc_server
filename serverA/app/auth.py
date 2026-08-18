from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import Settings, UserRecord


ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def issue_token(settings: Settings, username: str) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.server.jwt_ttl_hours)
    payload = {
        "sub": username,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expires_at


def parse_token(settings: Settings, token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("invalid token") from exc
    username = payload.get("sub")
    if not username or username not in settings.users:
        raise AuthError("invalid token")
    return str(username)


def authenticate(settings: Settings, username: str, password: str) -> UserRecord:
    user = settings.users.get(username)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid credentials")
    return user
