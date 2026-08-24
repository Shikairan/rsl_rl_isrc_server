"""SQLite user-container registry."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.models import SCHEMA_SQL, ContainerRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Registry:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(SCHEMA_SQL)
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(containers)").fetchall()}
            if "obs_host_port" not in cols:
                conn.execute("ALTER TABLE containers ADD COLUMN obs_host_port INTEGER")
            if "tb_host_port" not in cols:
                conn.execute("ALTER TABLE containers ADD COLUMN tb_host_port INTEGER")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, username: str) -> ContainerRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM containers WHERE username = ?", (username,)
            ).fetchone()
        return self._row(row) if row else None

    def list_all(self) -> list[ContainerRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM containers").fetchall()
        return [self._row(r) for r in rows]

    def allocated_ports(self) -> set[int]:
        return {r.host_port for r in self.list_all()}

    def allocated_obs_ports(self) -> set[int]:
        return {r.obs_host_port for r in self.list_all() if r.obs_host_port is not None}

    def allocated_tb_ports(self) -> set[int]:
        return {r.tb_host_port for r in self.list_all() if r.tb_host_port is not None}

    def upsert(self, rec: ContainerRecord) -> None:
        rec.updated_at = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO containers (
                    username, container_id, container_name, host_port, obs_host_port, tb_host_port, image,
                    gpu_count, cpu, memory, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    container_id=excluded.container_id,
                    container_name=excluded.container_name,
                    host_port=excluded.host_port,
                    obs_host_port=excluded.obs_host_port,
                    tb_host_port=excluded.tb_host_port,
                    image=excluded.image,
                    gpu_count=excluded.gpu_count,
                    cpu=excluded.cpu,
                    memory=excluded.memory,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    rec.username,
                    rec.container_id,
                    rec.container_name,
                    rec.host_port,
                    rec.obs_host_port,
                    rec.tb_host_port,
                    rec.image,
                    rec.gpu_count,
                    rec.cpu,
                    rec.memory,
                    rec.status,
                    rec.created_at or _now(),
                    rec.updated_at,
                ),
            )
            conn.commit()

    def delete(self, username: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM containers WHERE username = ?", (username,))
            conn.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> ContainerRecord:
        return ContainerRecord(
            username=row["username"],
            container_id=row["container_id"],
            container_name=row["container_name"],
            host_port=int(row["host_port"]),
            obs_host_port=row["obs_host_port"] if row["obs_host_port"] is not None else None,
            tb_host_port=row["tb_host_port"] if "tb_host_port" in row.keys() and row["tb_host_port"] is not None else None,
            image=row["image"],
            gpu_count=int(row["gpu_count"]),
            cpu=row["cpu"],
            memory=row["memory"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
