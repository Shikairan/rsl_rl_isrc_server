"""Port pool 31000-31999, persisted via registry in-use set."""

from __future__ import annotations

import threading


class PortPoolExhausted(RuntimeError):
    pass


class PortPool:
    def __init__(self, start: int, end: int, in_use: set[int] | None = None) -> None:
        self.start = start
        self.end = end
        self._in_use: set[int] = set(in_use or [])
        self._lock = threading.Lock()

    def allocate(self) -> int:
        with self._lock:
            for port in range(self.start, self.end + 1):
                if port not in self._in_use:
                    self._in_use.add(port)
                    return port
            raise PortPoolExhausted(f"port pool exhausted ({self.start}-{self.end})")

    def release(self, port: int) -> None:
        with self._lock:
            self._in_use.discard(port)

    def reserve(self, port: int) -> None:
        with self._lock:
            self._in_use.add(port)
