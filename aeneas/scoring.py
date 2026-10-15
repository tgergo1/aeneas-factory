"""Ranking candidates by how well they match the prompt: SigLIP for images, CLAP for sound.
Optional: needs `make scoring` (torch, transformers) and `make models-scoring`. Without them the
factory still runs and candidates are ranked by the automatic checks only.

The models run in a separate worker process (aeneas.scoring_worker) that exits after five idle
minutes, so the service itself never holds torch or the weights: it stays at about 40 MB."""
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import wave

import numpy as np

from . import registry

# Keep library logs and progress bars out of the factory's output.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)

IMAGE_MODEL, AUDIO_MODEL = "siglip-base-p16", "clap-htsat"
IDLE_SECONDS = int(os.environ.get("AEN_SCORING_IDLE", 300))  # the worker exits after five idle minutes


def available(kind):
    """Installed and downloaded? Checked without importing torch (which would cost the caller ~300 MB)."""
    if not (importlib.util.find_spec("torch") and importlib.util.find_spec("transformers")):
        return False
    return registry.is_downloaded(IMAGE_MODEL if kind == "image" else AUDIO_MODEL)


# ---------------------------------------------------------------- the worker, seen from the caller

class _Worker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.calibration = None

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def call(self, req):
        with self.lock:
            for attempt in (1, 2):  # the worker may have exited while idle: start it again once
                if not self.alive():
                    root = str(registry.ROOT)
                    self.proc = subprocess.Popen(
                        [sys.executable, "-m", "aeneas.scoring_worker", str(IDLE_SECONDS)], cwd=root, text=True,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        env={**os.environ, "PYTHONPATH": root + os.pathsep + os.environ.get("PYTHONPATH", "")})
                    if not json.loads(self.proc.stdout.readline() or "{}").get("ready"):
                        self.stop()
                        raise RuntimeError("the scoring worker did not start")
                try:
                    self.proc.stdin.write(json.dumps(req) + "\n")
                    self.proc.stdin.flush()
                    line = self.proc.stdout.readline()
                except BrokenPipeError:
                    line = ""
                if line:
                    reply = json.loads(line)
                    if not reply.get("ok"):
                        raise RuntimeError(reply.get("error"))
                    return reply
                self.stop()
            raise RuntimeError("the scoring worker stopped unexpectedly")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


_worker = _Worker()


def loaded():
    return ["siglip/clap worker"] if _worker.alive() else []


def unload():
    """Stop the worker now, freeing its memory; the next use starts it again (a few seconds)."""
    was = _worker.alive()
    _worker.stop()
    return was


def image_embeddings(paths):
    return np.asarray(_worker.call({"op": "image", "paths": [os.path.abspath(p) for p in paths]})["vectors"], dtype=np.float32)


def text_embeddings(texts):
    return np.asarray(_worker.call({"op": "text", "texts": list(texts)})["vectors"], dtype=np.float32)


def match_probability(cosines):
    """SigLIP's own calibrated probability that an image matches a text, from cosine similarities."""
    if _worker.calibration is None:
        r = _worker.call({"op": "calibration"})
        _worker.calibration = (r["scale"], r["bias"])
    scale, bias = _worker.calibration
    c = np.asarray(cosines, dtype=np.float64)
    return (1 / (1 + np.exp(-(c * scale + bias)))).tolist()


def image_scores(paths, text):
    """Cosine similarity of each image to the text; higher is a better match (ranking only)."""
    return (image_embeddings(paths) @ text_embeddings([text])[0]).tolist()


def audio_scores(paths, text):
    return _worker.call({"op": "audio_scores", "paths": [os.path.abspath(p) for p in paths], "text": text})["scores"]


# ---------------------------------------------------------------- inside the worker

_models = {}


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _siglip():
    if "siglip" not in _models:
        from transformers import AutoModel, AutoProcessor
        path = registry.model_path(IMAGE_MODEL)
        _models["siglip"] = (AutoModel.from_pretrained(path).eval().to(_device()), AutoProcessor.from_pretrained(path))
    return _models["siglip"]


def _clap():
    if "clap" not in _models:
        from transformers import ClapModel, ClapProcessor
        path = registry.model_path(AUDIO_MODEL)
        _models["clap"] = (ClapModel.from_pretrained(path).eval().to(_device()), ClapProcessor.from_pretrained(path))
    return _models["clap"]


def _norm(t):
    t = t.detach().float().cpu().numpy()
    return t / np.linalg.norm(t, axis=-1, keepdims=True)


def _features(out):
    """transformers returns a tensor or, in newer versions, an output object with the pooled embedding."""
    return getattr(out, "pooler_output", None) if not hasattr(out, "detach") else out


def _local_image_embeddings(paths):
    import torch
    from PIL import Image
    model, proc = _siglip()
    ims = [Image.open(p).convert("RGB") for p in paths]
    with torch.no_grad():
        x = proc(images=ims, return_tensors="pt").to(_device())
        return _norm(_features(model.get_image_features(**x)))


def _local_text_embeddings(texts):
    import torch
    model, proc = _siglip()
    with torch.no_grad():  # SigLIP was trained with texts padded to 64 tokens
        x = proc(text=texts, return_tensors="pt", padding="max_length", max_length=64, truncation=True).to(_device())
        return _norm(_features(model.get_text_features(**x)))


def _read_wav(path, rate=48000):
    with wave.open(str(path), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        ch, sr = w.getnchannels(), w.getframerate()
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != rate and x.size:
        t = np.linspace(0, len(x) - 1, int(len(x) * rate / sr))
        x = np.interp(t, np.arange(len(x)), x).astype(np.float32)
    return x


def _local_audio_scores(paths, text):
    import torch
    model, proc = _clap()
    audios = [_read_wav(p) for p in paths]
    with torch.no_grad():
        a = proc(audio=audios, sampling_rate=48000, return_tensors="pt").to(_device())
        t = proc(text=[text], return_tensors="pt", padding=True).to(_device())
        ae = _norm(_features(model.get_audio_features(**a)))
        te = _norm(_features(model.get_text_features(**t)))
    return (ae @ te[0]).tolist()
