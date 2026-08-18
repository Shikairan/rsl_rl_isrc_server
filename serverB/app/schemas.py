from __future__ import annotations

from pydantic import BaseModel, Field


class TaskStartRequest(BaseModel):
    script_path: str
    torchrun_args: list[str] = Field(default_factory=list)
    script_args: list[str] = Field(default_factory=list)


class TaskStartResponse(BaseModel):
    task_id: str
    status: str
    started_at: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    exit_code: int | None = None
    started_at: str
    finished_at: str | None = None


class TaskLogsResponse(BaseModel):
    next_offset: int
    lines: list[str]


class StopResponse(BaseModel):
    status: str


class ErrorBody(BaseModel):
    error: str
