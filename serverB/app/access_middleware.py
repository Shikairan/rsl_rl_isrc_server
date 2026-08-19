"""HTTP access log. Never logs Authorization, body, or passwords."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_setup import ACCESS_LOGGER_NAME

logger = logging.getLogger(ACCESS_LOGGER_NAME)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
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
                    "%s %s %s %.1fms",
                    request.method,
                    request.url.path,
                    status,
                    duration_ms,
                )
            except Exception:
                pass
