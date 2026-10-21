"""MOSS-SoundEffect. On Apple Silicon through a persistent MLX worker: the model loads once and stays in
memory until it has been idle for a while (it holds about 14 GB of GPU memory). Everywhere else through the
openmoss C++/GGML runtime (moss-tts-cli: CUDA, Vulkan, ROCm or CPU), one process per take."""
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from .. import host, registry
from ..paths import MOSS_PY, OPENMOSS_CLI, portable
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


def model_id():
    """The MOSS-SoundEffect variant for this machine: moss-sfx (MLX) or moss-sfx-gguf (openmoss)."""
    return registry.pick("moss-sfx", "moss-sfx-gguf")


def tool():
    return "moss-soundeffect-mlx" if model_id() == "moss-sfx" else "openmoss"


def generate(prompt, seconds, steps, cfg, seed, out, log_path, ctx):
    """One take. Returns the command to record in the provenance."""
    if model_id() == "moss-sfx":
        worker().generate(prompt, seconds, steps, cfg, seed, out, log_path, ctx.cancelled)
        return ["moss worker", f"seed={seed}"]
    if not OPENMOSS_CLI.exists():
        raise EngineError("openmoss is not built. Run: make moss  (python install.py moss)")
    registry.require("moss-sfx-gguf")
    cmd = [OPENMOSS_CLI, "--model", registry.model_path("moss-sfx-gguf", "moss-soundeffect-2.0.gguf"), "--text", prompt,
           "--seconds", str(seconds), "--steps", str(steps), "--cfg-scale", str(cfg), "--seed", str(seed), "--output", out]
    if host.gpu() == "vulkan":
        cmd.append("--vk-f32")  # f32 accumulation on Vulkan: f16 is 16x less accurate on the decoded waveform
    ctx.runner.run(cmd, log_path)
    if not Path(out).exists():
        raise EngineError(f"moss-tts-cli wrote no audio; see {portable(log_path)}")
    return cmd
