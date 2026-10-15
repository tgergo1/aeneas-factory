"""MOSS-SoundEffect through a persistent MLX worker: the model loads once and stays in memory
until it has been idle for a while (it holds about 14 GB of GPU memory)."""
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from .. import registry
from ..paths import MOSS_PY, portable
from . import Cancelled, EngineError

WORKER = Path(__file__).with_name("moss_worker.py")
IDLE_SECONDS = 300


class Worker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.last_used = 0.0
        self.log = None
        threading.Thread(target=self._reaper, daemon=True).start()

    def _start(self, log_path):
        if not MOSS_PY.exists():
            raise EngineError("The MOSS environment is not set up. Run: make moss")
        registry.require("moss-sfx")
        self.log = open(log_path, "a")
        self.proc = subprocess.Popen([str(MOSS_PY), str(WORKER), str(registry.model_path("moss-sfx"))],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True,
                                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        ready = self.proc.stdout.readline()
        if not ready or not json.loads(ready).get("ready"):
            self.stop()
            raise EngineError(f"the MOSS worker did not start; see {portable(log_path)}")

    def generate(self, prompt, seconds, steps, cfg, seed, out, log_path, cancel_flag=lambda: False):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start(log_path)
            if cancel_flag():
                raise Cancelled()
            req = {"prompt": prompt, "seconds": seconds, "steps": steps, "cfg": cfg, "seed": seed, "out": str(out)}
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            self.last_used = time.time()
        if not line:
            self.stop()
            raise Cancelled() if cancel_flag() else EngineError("the MOSS worker stopped unexpectedly")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise EngineError(f"MOSS: {reply.get('error')}")
        return reply

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def _reaper(self):
        while True:
            time.sleep(30)
            if self.proc and time.time() - self.last_used > IDLE_SECONDS and self.lock.acquire(blocking=False):
                try:
                    self.stop()
                finally:
                    self.lock.release()


_worker = None


def worker():
    global _worker
    if _worker is None:
        _worker = Worker()
    return _worker


def params(seconds, steps, cfg):
    return {"seconds": seconds, "steps": steps, "cfg": cfg, "sample_rate": 48000}
