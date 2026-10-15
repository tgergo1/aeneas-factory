"""Tests run without models or GPU. Each test session gets its own state folder."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["AEN_STATE"] = tempfile.mkdtemp(prefix="aen-test-state-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

GALLERY = Path(__file__).resolve().parent.parent / "docs" / "gallery"


def lfs_present(p):
    """Gallery files are in Git LFS; without git-lfs they are small pointer files."""
    return p.exists() and not p.read_bytes()[:40].startswith(b"version https://git-lfs")


@pytest.fixture
def noise_png(tmp_path):
    p = tmp_path / "noise.png"
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 255, (64, 64, 3), dtype=np.uint8)).save(p)
    return p


@pytest.fixture
def blank_png(tmp_path):
    p = tmp_path / "blank.png"
    Image.new("RGB", (512, 512), (254, 254, 254)).save(p)
    return p


def write_wav(path, x, rate=48000):
    import wave
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


@pytest.fixture
def tone_wav(tmp_path):
    t = np.linspace(0, 1, 48000, endpoint=False)
    return write_wav(tmp_path / "tone.wav", 0.3 * np.sin(2 * np.pi * 440 * t))


@pytest.fixture
def silent_wav(tmp_path):
    return write_wav(tmp_path / "silent.wav", np.zeros(48000))
