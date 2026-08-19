from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import LoggingSettings, ServerSettings, Settings
from app.logging_setup import ACCESS_LOGGER_NAME, setup_logging, shutdown_logging


def _settings(log_dir: Path, *, enabled: bool = True, console: bool = False) -> Settings:
    server = ServerSettings(
        logging=LoggingSettings(
            enabled=enabled,
            dir=str(log_dir),
            level="INFO",
            console=console,
            access_log=True,
            max_bytes=1_048_576,
            backup_count=2,
        )
    )
    return Settings(server=server, users={})


def test_setup_writes_app_and_access_logs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERVER_A_LOG_ENABLED", raising=False)
    monkeypatch.delenv("SERVER_A_LOG_DIR", raising=False)
    shutdown_logging()
    log_dir = tmp_path / "logs"
    settings = _settings(log_dir)
    setup_logging(settings)

    logging.getLogger("server_a").info("hello-app-log")
    logging.getLogger(ACCESS_LOGGER_NAME).info("GET /health 200 1.0ms user=-")

    # QueueListener is async; wait briefly for flush
    deadline = time.time() + 2.0
    app_log = log_dir / "serverA.log"
    access_log = log_dir / "access.log"
    while time.time() < deadline:
        if app_log.is_file() and access_log.is_file():
            if "hello-app-log" in app_log.read_text(encoding="utf-8") and (
                "GET /health" in access_log.read_text(encoding="utf-8")
            ):
                break
        time.sleep(0.05)
    else:
        raise AssertionError(
            f"logs missing or incomplete app={app_log.exists()} access={access_log.exists()}"
        )

    assert "hello-app-log" in app_log.read_text(encoding="utf-8")
    assert "GET /health" in access_log.read_text(encoding="utf-8")
    shutdown_logging()


def test_setup_disabled_creates_no_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERVER_A_LOG_DIR", raising=False)
    shutdown_logging()
    log_dir = tmp_path / "logs-off"
    settings = _settings(log_dir, enabled=False)
    setup_logging(settings)
    logging.getLogger("server_a").info("should-not-file")
    time.sleep(0.1)
    assert not log_dir.exists() or not any(log_dir.iterdir())
    shutdown_logging()


def test_setup_unwritable_dir_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SERVER_A_LOG_ENABLED", raising=False)
    monkeypatch.delenv("SERVER_A_LOG_DIR", raising=False)
    shutdown_logging()
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o000)
    try:
        settings = _settings(blocked / "nested" / "logs")
        setup_logging(settings)  # must not raise
        logging.getLogger("server_a").info("still-ok")
    finally:
        blocked.chmod(0o755)
        shutdown_logging()
