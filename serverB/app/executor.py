from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from app.log_store import LogStore


class Executor:
    def __init__(self, launcher: str, workspace: Path, stop_grace_sec: float) -> None:
        self.launcher = launcher
        self.workspace = workspace
        self.stop_grace_sec = stop_grace_sec

    def spawn(
        self,
        script: Path,
        torchrun_args: list[str],
        script_args: list[str],
        logs: LogStore,
    ) -> subprocess.Popen[str]:
        cmd = [self.launcher, *torchrun_args, str(script), *script_args]
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            bufsize=1,
        )
        threading.Thread(target=self._pump, args=(proc, logs), daemon=True).start()
        return proc

    def _pump(self, proc: subprocess.Popen[str], logs: LogStore) -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                logs.append(line)
        finally:
            proc.stdout.close()

    def terminate_group(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        pgid = os.getpgid(proc.pid)
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.time() + self.stop_grace_sec
        while time.time() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.05)
        if proc.poll() is None:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
