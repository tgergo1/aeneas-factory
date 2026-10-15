"""Ranking candidates by how well they match the prompt: SigLIP for images, CLAP for sound.
Optional: needs `make scoring` (torch, transformers) and `make models-scoring`. Without them the
factory still runs and candidates are ranked by the automatic checks only."""
import functools
import logging
import os
import wave

import numpy as np

# Keep library logs and progress bars out of the factory's output.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)

from . import registry

IMAGE_MODEL, AUDIO_MODEL = "siglip-base-p16", "clap-htsat"


def available(kind):
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return registry.is_downloaded(IMAGE_MODEL if kind == "image" else AUDIO_MODEL)


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


@functools.lru_cache(maxsize=1)
def _siglip():
    from transformers import AutoModel, AutoProcessor
    path = registry.model_path(IMAGE_MODEL)
    model = AutoModel.from_pretrained(path).eval().to(_device())
    return model, AutoProcessor.from_pretrained(path)


@functools.lru_cache(maxsize=1)
def _clap():
    from transformers import ClapModel, ClapProcessor
    path = registry.model_path(AUDIO_MODEL)
    model = ClapModel.from_pretrained(path).eval().to(_device())
    return model, ClapProcessor.from_pretrained(path)


def _norm(t):
    t = t.detach().float().cpu().numpy()
    return t / np.linalg.norm(t, axis=-1, keepdims=True)


def _features(out):
    """transformers returns a tensor or, in newer versions, an output object with the pooled embedding."""
    return getattr(out, "pooler_output", None) if not hasattr(out, "detach") else out


def image_embeddings(paths):
    import torch
    from PIL import Image
    model, proc = _siglip()
    ims = [Image.open(p).convert("RGB") for p in paths]
    with torch.no_grad():
        x = proc(images=ims, return_tensors="pt").to(_device())
        return _norm(_features(model.get_image_features(**x)))


def text_embeddings(texts):
    import torch
    model, proc = _siglip()
    with torch.no_grad():  # SigLIP was trained with texts padded to 64 tokens
        x = proc(text=texts, return_tensors="pt", padding="max_length", max_length=64, truncation=True).to(_device())
        return _norm(_features(model.get_text_features(**x)))


def match_probability(cosines):
    """SigLIP's own calibrated probability that an image matches a text, from cosine similarities."""
    model, _ = _siglip()
    scale, bias = float(model.logit_scale.detach().exp()), float(model.logit_bias.detach())
    c = np.asarray(cosines, dtype=np.float64)
    return (1 / (1 + np.exp(-(c * scale + bias)))).tolist()


def image_scores(paths, text):
    """Cosine similarity of each image to the text; higher is a better match (ranking only)."""
    return (image_embeddings(paths) @ text_embeddings([text])[0]).tolist()


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


def audio_scores(paths, text):
    import torch
    model, proc = _clap()
    audios = [_read_wav(p) for p in paths]
    with torch.no_grad():
        a = proc(audio=audios, sampling_rate=48000, return_tensors="pt").to(_device())
        t = proc(text=[text], return_tensors="pt", padding=True).to(_device())
        ae = _norm(_features(model.get_audio_features(**a)))
        te = _norm(_features(model.get_text_features(**t)))
    return (ae @ te[0]).tolist()
