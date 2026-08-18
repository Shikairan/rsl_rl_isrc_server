from __future__ import annotations

from pathlib import Path

from app.path_guard import PathGuardError, resolve_script


def test_relative_ok(tmp_path: Path) -> None:
    script = tmp_path / "jobs" / "a.py"
    script.parent.mkdir()
    script.write_text("print(1)\n", encoding="utf-8")
    assert resolve_script(tmp_path, "jobs/a.py") == script.resolve()


def test_parent_escape(tmp_path: Path) -> None:
    (tmp_path / "jobs").mkdir()
    try:
        resolve_script(tmp_path, "../etc/passwd")
        assert False
    except PathGuardError:
        pass


def test_absolute_rejected(tmp_path: Path) -> None:
    try:
        resolve_script(tmp_path, "/etc/passwd")
        assert False
    except PathGuardError:
        pass


def test_dotdot_in_jobs(tmp_path: Path) -> None:
    (tmp_path / "jobs").mkdir()
    try:
        resolve_script(tmp_path, "jobs/../../etc/passwd")
        assert False
    except PathGuardError:
        pass
