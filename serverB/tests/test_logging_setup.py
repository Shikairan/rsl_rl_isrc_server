from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import Settings
from app.logging_setup import ACCESS_LOGGER_NAME, setup_logging, shutdown_logging


def _settings(log_dir: Path, *, enabled: bool = True, console: bool = False) -> Settings:
    return Settings(
        workspace_root=log_dir.parent,
        launcher="python3",
        stop_grace_sec=1.0,
        host="0.0.0.0",
        port=8080,
        log_enabled=enabled,
        log_dir=log_dir,
        log_level="INFO",
        log_console=console,
        log_access=True,
        log_max_bytes=1_048_576,
        log_backup_count=2,
    )


def test_setup_writes_app_and_access_logs(tmp_path: Path) -> None:
    shutdown_logging()
    log_dir = tmp_path / "logs"
    setup_logging(_settings(log_dir))
    logging.getLogger("server_b").info("hello-sb-log")
    logging.getLogger(ACCESS_LOGGER_NAME).info("GET /health 200 1.0ms")

    deadline = time.time() + 2.0
    app_log = log_dir / "serverB.log"
    access_log = log_dir / "serverB-access.log"
    while time.time() < deadline:
        if app_log.is_file() and access_log.is_file():
            app_txt = app_log.read_text(encoding="utf-8")
            acc_txt = access_log.read_text(encoding="utf-8")
            if "hello-sb-log" in app_txt and "GET /health" in acc_txt:
                break
        time.sleep(0.05)
    else:
        raise AssertionError("server B log files missing or incomplete")
    shutdown_logging()


def test_setup_disabled_creates_no_files(tmp_path: Path) -> None:
    shutdown_logging()
    log_dir = tmp_path / "logs-off"
    setup_logging(_settings(log_dir, enabled=False))
    logging.getLogger("server_b").info("should-not-file")
    time.sleep(0.1)
    assert not log_dir.exists() or not any(log_dir.iterdir())
    shutdown_logging()


def test_setup_unwritable_dir_does_not_raise(tmp_path: Path) -> None:
    shutdown_logging()
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o000)
    try:
        setup_logging(_settings(blocked / "nested" / "logs"))
        logging.getLogger("server_b").info("still-ok")
    finally:
        blocked.chmod(0o755)
        shutdown_logging()
