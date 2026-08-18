from __future__ import annotations

import threading


class LogStore:
    """In-memory log buffer. Offset is character index into the concatenated text."""

    def __init__(self) -> None:
        self._buf = ""
        self._lock = threading.Lock()

    def append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._buf += text

    def read_since(self, offset: int) -> tuple[list[str], int]:
        with self._lock:
            if offset < 0:
                offset = 0
            if offset > len(self._buf):
                offset = len(self._buf)
            chunk = self._buf[offset:]
            next_offset = len(self._buf)
        lines = chunk.splitlines()
        return lines, next_offset

    def clear(self) -> None:
        with self._lock:
            self._buf = ""
