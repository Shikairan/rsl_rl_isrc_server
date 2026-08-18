from __future__ import annotations

from dataclasses import dataclass


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS containers (
    username       TEXT PRIMARY KEY,
    container_id   TEXT NOT NULL,
    container_name TEXT NOT NULL,
    host_port      INTEGER NOT NULL,
    obs_host_port  INTEGER,
    image          TEXT NOT NULL,
    gpu_count      INTEGER NOT NULL,
    cpu            TEXT,
    memory         TEXT,
    status         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
"""


@dataclass
class ContainerRecord:
    username: str
    container_id: str
    container_name: str
    host_port: int
    obs_host_port: int | None
    image: str
    gpu_count: int
    cpu: str | None
    memory: str | None
    status: str
    created_at: str
    updated_at: str
