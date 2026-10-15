"""Engines: thin adapters over the tools that do the work. Each builds a command or talks to a
worker, writes the tool's output to a log, and returns the paths it made. Checks, provenance,
policy and the library are applied above them, in aeneas.ops."""
import os
import signal
import subprocess
import threading
from pathlib import Path

from ..paths import portable


class EngineError(Exception):
    pass


class Cancelled(Exception):
    pass


class Runner:
    """Runs one external process at a time for a job, so the job can be cancelled."""

    def __init__(self):
        self.proc = None
        self.cancelled = False
        self.lock = threading.Lock()

    def run(self, cmd, log_path, env=None, cwd=None):
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as log:
            log.write("$ " + " ".join(portable(c) for c in cmd) + "\n\n")
            log.flush()
            with self.lock:
                if self.cancelled:
                    raise Cancelled()
                self.proc = subprocess.Popen([str(c) for c in cmd], stdout=log, stderr=subprocess.STDOUT,
                                             env={**os.environ, **(env or {})}, cwd=cwd, start_new_session=True)
            code = self.proc.wait()
            with self.lock:
                self.proc = None
        if self.cancelled:
            raise Cancelled()
        if code != 0:
            tail = log_path.read_text(errors="replace").splitlines()[-20:]
            raise EngineError(f"{Path(str(cmd[0])).name} failed (exit {code}). End of {portable(log_path)}:\n"
                              + "\n".join(tail))

    def cancel(self):
        with self.lock:
            self.cancelled = True
            if self.proc and self.proc.poll() is None:
                try:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
