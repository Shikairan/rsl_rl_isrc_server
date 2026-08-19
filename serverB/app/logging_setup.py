"""Queue-based async file logging for Server B. Setup failures never raise."""

from __future__ import annotations

import atexit
import logging
import logging.handlers
import sys
from queue import SimpleQueue
from typing import Any

from app.config import Settings

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_app_listener: logging.handlers.QueueListener | None = None
_access_listener: logging.handlers.QueueListener | None = None
_configured = False
_atexit_registered = False

ACCESS_LOGGER_NAME = "server_b.access"


def _level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO)


def shutdown_logging() -> None:
    global _app_listener, _access_listener, _configured
    for listener in (_access_listener, _app_listener):
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
    _app_listener = None
    _access_listener = None
    _configured = False


def setup_logging(settings: Settings) -> None:
    """Attach queue + rotating file handlers under workspace/logs. Never raises."""
    global _app_listener, _access_listener, _configured, _atexit_registered
    if _configured:
        return

    level = _level(settings.log_level)
    fmt = logging.Formatter(_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(level)

    if not settings.log_enabled:
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(console)
        root.setLevel(level)
        access = logging.getLogger(ACCESS_LOGGER_NAME)
        access.handlers.clear()
        access.propagate = False
        access.setLevel(level)
        _configured = True
        return

    try:
        log_dir = settings.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        app_file = logging.handlers.RotatingFileHandler(
            log_dir / "serverB.log",
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
            delay=True,
        )
        app_file.setFormatter(fmt)
        app_file.setLevel(level)

        app_queue: SimpleQueue[Any] = SimpleQueue()
        app_qh = logging.handlers.QueueHandler(app_queue)

        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(app_qh)
        root.setLevel(level)

        app_dest: list[logging.Handler] = [app_file]
        if settings.log_console:
            app_dest.append(console)
        _app_listener = logging.handlers.QueueListener(
            app_queue, *app_dest, respect_handler_level=True
        )
        _app_listener.start()

        access = logging.getLogger(ACCESS_LOGGER_NAME)
        access.handlers.clear()
        access.propagate = False
        access.setLevel(level)

        if settings.log_access:
            access_file = logging.handlers.RotatingFileHandler(
                log_dir / "serverB-access.log",
                maxBytes=settings.log_max_bytes,
                backupCount=settings.log_backup_count,
                encoding="utf-8",
                delay=True,
            )
            access_file.setFormatter(fmt)
            access_file.setLevel(level)

            access_queue: SimpleQueue[Any] = SimpleQueue()
            access_qh = logging.handlers.QueueHandler(access_queue)
            access.addHandler(access_qh)

            access_dest: list[logging.Handler] = [access_file]
            if settings.log_console:
                access_dest.append(console)
            _access_listener = logging.handlers.QueueListener(
                access_queue, *access_dest, respect_handler_level=True
            )
            _access_listener.start()

        for name in ("uvicorn", "uvicorn.error"):
            ug = logging.getLogger(name)
            ug.handlers.clear()
            ug.propagate = True
            ug.setLevel(level)

        ua = logging.getLogger("uvicorn.access")
        ua.handlers.clear()
        ua.propagate = False
        ua.setLevel(logging.CRITICAL)

        if not _atexit_registered:
            atexit.register(shutdown_logging)
            _atexit_registered = True

        _configured = True
        logging.getLogger("server_b").info(
            "logging ready dir=%s level=%s access=%s",
            log_dir,
            settings.log_level,
            settings.log_access,
        )
    except Exception as exc:
        try:
            shutdown_logging()
        except Exception:
            pass
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(console)
        root.setLevel(level)
        access = logging.getLogger(ACCESS_LOGGER_NAME)
        access.handlers.clear()
        access.propagate = False
        _configured = True
        logging.getLogger("server_b").warning(
            "file logging disabled, console only: %s", exc
        )
