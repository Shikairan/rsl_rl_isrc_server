from __future__ import annotations

import logging
import time
from pathlib import Path

from obsserver.logging_setup import setup_logging, shutdown_logging


def test_obs_setup_writes_file(tmp_path: Path, monkeypatch) -> None:
    shutdown_logging()
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("OBS_LOG_ENABLED", "1")
    monkeypatch.setenv("OBS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("OBS_LOG_CONSOLE", "0")
    setup_logging()
    logging.getLogger("obsserver").info("hello-obs-log")

    path = log_dir / "obsserver.log"
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if path.is_file() and "hello-obs-log" in path.read_text(encoding="utf-8"):
            break
        time.sleep(0.05)
    else:
        raise AssertionError("obsserver.log missing or incomplete")
    text = path.read_text(encoding="utf-8")
    assert "hello-obs-log" in text
    shutdown_logging()


def test_obs_setup_unwritable_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    shutdown_logging()
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o000)
    monkeypatch.setenv("OBS_LOG_ENABLED", "1")
    monkeypatch.setenv("OBS_LOG_DIR", str(blocked / "nested" / "logs"))
    try:
        setup_logging()
        logging.getLogger("obsserver").info("still-ok")
    finally:
        blocked.chmod(0o755)
        shutdown_logging()
