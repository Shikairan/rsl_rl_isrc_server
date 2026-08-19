"""HTTP access log middleware. Never logs Authorization, body, or passwords."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_setup import ACCESS_LOGGER_NAME

logger = logging.getLogger(ACCESS_LOGGER_NAME)


def _peek_user(request: Request) -> str:
    """Best-effort username from Bearer JWT without failing the request."""
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return "-"
    token = auth[7:].strip()
    if not token:
        return "-"
    try:
        import jwt

        settings = getattr(request.app.state, "settings", None)
        if settings is None:
            return "-"
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        sub = payload.get("sub")
        return str(sub) if sub else "-"
    except Exception:
        return "-"


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        user = _peek_user(request)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            status = 500
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000.0
            try:
                logger.info(
                    "%s %s %s %.1fms user=%s",
                    request.method,
                    request.url.path,
                    status,
                    duration_ms,
                    user,
                )
            except Exception:
                pass
