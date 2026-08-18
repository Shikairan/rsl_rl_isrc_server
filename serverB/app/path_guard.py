from __future__ import annotations

from pathlib import Path


class PathGuardError(Exception):
    pass


def resolve_script(workspace_root: Path, script_path: str) -> Path:
    """Resolve script_path under workspace. Reject absolute paths and escapes."""
    if not script_path or script_path.strip() != script_path:
        raise PathGuardError("script_path is empty or has surrounding whitespace")
    raw = Path(script_path)
    if raw.is_absolute() or script_path.startswith("/") or script_path.startswith("~"):
        raise PathGuardError("script_path must be relative to workspace")
    workspace = workspace_root.resolve()
    candidate = (workspace / script_path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise PathGuardError("script_path escapes workspace") from exc
    if not candidate.is_file():
        raise PathGuardError("script_path not found in workspace")
    return candidate
