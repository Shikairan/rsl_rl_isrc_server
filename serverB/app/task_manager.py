from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import Settings
from app.executor import Executor
from app.log_store import LogStore
from app.path_guard import PathGuardError, resolve_script

logger = logging.getLogger(__name__)


class TaskConflict(Exception):
    pass


class TaskNotFound(Exception):
    pass


class LogsGone(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    task_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    exit_code: int | None = None
    logs: LogStore | None = None
    proc: object | None = None
    stop_requested: bool = False


class TaskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = Executor(settings.launcher, settings.workspace_root, settings.stop_grace_sec)
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._current: Task | None = None
        self._history: dict[str, Task] = {}

    def _running(self) -> Task | None:
        task = self._current
        if task is not None and task.status == "running":
            return task
        return None

    def start(self, script_path: str, torchrun_args: list[str], script_args: list[str]) -> Task:
        script = resolve_script(self.settings.workspace_root, script_path)
        with self._lock:
            if self._running() is not None:
                logger.warning("task start conflict script_path=%s", script_path)
                raise TaskConflict("a task is already running")
            logs = LogStore()
            proc = self.executor.spawn(script, torchrun_args, script_args, logs)
            task = Task(
                task_id=f"t-{next(self._ids)}",
                status="running",
                started_at=_now(),
                logs=logs,
                proc=proc,
            )
            self._current = task
            self._history[task.task_id] = task
            threading.Thread(target=self._wait, args=(task,), daemon=True).start()
            logger.info("task start task_id=%s script_path=%s", task.task_id, script_path)
            return task

    def _wait(self, task: Task) -> None:
        proc = task.proc
        assert proc is not None
        code = proc.wait()
        with self._lock:
            if task.status != "running":
                return
            task.exit_code = code
            task.finished_at = _now()
            if task.stop_requested:
                task.status = "stopped"
            elif code == 0:
                task.status = "succeeded"
            else:
                task.status = "failed"
            logger.info(
                "task finished task_id=%s status=%s exit_code=%s",
                task.task_id,
                task.status,
                task.exit_code,
            )
            task.logs = None
            task.proc = None

    def status(self, task_id: str) -> Task:
        with self._lock:
            task = self._history.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            return task

    def logs(self, task_id: str, since: int) -> tuple[list[str], int]:
        with self._lock:
            task = self._history.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.logs is None:
                raise LogsGone(task_id)
            store = task.logs
        return store.read_since(since)

    def stop(self, task_id: str) -> str:
        with self._lock:
            task = self._history.get(task_id)
            if task is None:
                raise TaskNotFound(task_id)
            if task.status != "running":
                return "stopped"
            logger.info("task stop task_id=%s", task_id)
            task.stop_requested = True
            proc = task.proc
        if proc is not None:
            self.executor.terminate_group(proc)  # type: ignore[arg-type]
        with self._lock:
            if task.status == "running":
                task.status = "stopped"
                task.finished_at = task.finished_at or _now()
                task.logs = None
                if proc is not None:
                    task.exit_code = proc.poll()
                task.proc = None
        return "stopped"

    def shutdown(self) -> None:
        running = self._running()
        if running is not None:
            try:
                self.stop(running.task_id)
            except TaskNotFound:
                pass
