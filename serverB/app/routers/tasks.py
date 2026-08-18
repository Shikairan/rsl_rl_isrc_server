from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.path_guard import PathGuardError
from app.schemas import (
    StopResponse,
    TaskLogsResponse,
    TaskStartRequest,
    TaskStartResponse,
    TaskStatusResponse,
)
from app.task_manager import LogsGone, TaskConflict, TaskNotFound

router = APIRouter()


def _mgr(request: Request):
    return request.app.state.tasks


@router.post("/tasks/start", response_model=TaskStartResponse, status_code=202)
def start_task(body: TaskStartRequest, request: Request) -> TaskStartResponse:
    try:
        task = _mgr(request).start(body.script_path, body.torchrun_args, body.script_args)
    except PathGuardError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    except TaskConflict as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    return TaskStartResponse(task_id=task.task_id, status=task.status, started_at=task.started_at)


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
def task_status(task_id: str, request: Request) -> TaskStatusResponse:
    try:
        task = _mgr(request).status(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail={"error": "task not found"}) from None
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        exit_code=task.exit_code,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


@router.get("/tasks/{task_id}/logs", response_model=TaskLogsResponse)
def task_logs(task_id: str, request: Request, since: int = Query(default=0)) -> TaskLogsResponse:
    try:
        lines, next_offset = _mgr(request).logs(task_id, since)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail={"error": "task not found"}) from None
    except LogsGone:
        raise HTTPException(status_code=404, detail={"error": "logs released"}) from None
    return TaskLogsResponse(next_offset=next_offset, lines=lines)


@router.post("/tasks/{task_id}/stop", response_model=StopResponse)
def stop_task(task_id: str, request: Request) -> StopResponse:
    try:
        status = _mgr(request).stop(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail={"error": "task not found"}) from None
    return StopResponse(status=status)
