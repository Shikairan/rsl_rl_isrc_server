"""Queue-based async file logging for obsserver. Never log frame payloads. Never raise."""

from __future__ import annotations

import atexit
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from queue import SimpleQueue
from typing import Any

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_listener: logging.handlers.QueueListener | None = None
_configured = False
_atexit_registered = False


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO)


def shutdown_logging() -> None:
    global _listener, _configured
    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None
    _configured = False


def setup_logging() -> None:
    global _listener, _configured, _atexit_registered
    if _configured:
        return

    enabled = _env_flag("OBS_LOG_ENABLED", True)
    level = _level(os.environ.get("OBS_LOG_LEVEL", "INFO"))
    console_on = _env_flag("OBS_LOG_CONSOLE", True)
    fmt = logging.Formatter(_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    console.setLevel(level)

    if not enabled:
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(console)
        root.setLevel(level)
        _configured = True
        return

    try:
        raw_dir = os.environ.get("OBS_LOG_DIR", "").strip()
        log_dir = Path(raw_dir) if raw_dir else Path("/workspace/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.environ.get("OBS_LOG_MAX_BYTES", str(10_485_760)))
        backup_count = int(os.environ.get("OBS_LOG_BACKUP_COUNT", "5"))

        app_file = logging.handlers.RotatingFileHandler(
            log_dir / "obsserver.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
        app_file.setFormatter(fmt)
        app_file.setLevel(level)

        queue: SimpleQueue[Any] = SimpleQueue()
        qh = logging.handlers.QueueHandler(queue)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(qh)
        root.setLevel(level)

        dest: list[logging.Handler] = [app_file]
        if console_on:
            dest.append(console)
        _listener = logging.handlers.QueueListener(queue, *dest, respect_handler_level=True)
        _listener.start()

        if not _atexit_registered:
            atexit.register(shutdown_logging)
            _atexit_registered = True

        _configured = True
        logging.getLogger("obsserver").info("logging ready dir=%s", log_dir)
    except Exception as exc:
        try:
            shutdown_logging()
        except Exception:
            pass
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(console)
        root.setLevel(level)
        _configured = True
        logging.getLogger("obsserver").warning(
            "file logging disabled, console only: %s", exc
        )
