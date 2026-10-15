import json
import shutil

import numpy as np
import pytest
from PIL import Image

from aeneas import checks, provenance
from conftest import GALLERY, lfs_present


def test_blank_image_fails(blank_png):
    with pytest.raises(checks.CheckFailed, match="blank"):
        checks.image(blank_png)


def test_real_image_passes(noise_png):
    assert checks.image(noise_png)["spread"] > 4


def test_silent_audio_fails(silent_wav):
    with pytest.raises(checks.CheckFailed, match="silent"):
        checks.audio(silent_wav)


def test_tone_passes(tone_wav):
    r = checks.audio(tone_wav)
    assert r["seconds"] == 1.0 and r["rms_dbfs"] > -20
    json.dumps(r)  # plain numbers only


def test_seam_check(tmp_path):
    rng = np.random.default_rng(1)
    k = np.fft.fftfreq(128)
    spec = rng.normal(size=(128, 128)) / (1e-3 + np.hypot(*np.meshgrid(k, k)))
    tile = np.real(np.fft.ifft2(spec))  # periodic: wraps perfectly
    tile = ((tile - tile.min()) / np.ptp(tile) * 255).astype(np.uint8)
    good, bad = tmp_path / "good.png", tmp_path / "bad.png"
    Image.fromarray(tile).save(good)
    Image.fromarray(np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (128, 1))).save(bad)  # jumps at the edge
    assert checks.seamless(good)["seam_ratio"] < 1.6
    with pytest.raises(checks.CheckFailed, match="seam"):
        checks.seamless(bad)


@pytest.mark.skipif(not lfs_present(GALLERY / "chest.glb"), reason="gallery not fetched from Git LFS")
def test_mesh_check_on_gallery_model():
    r = checks.mesh(GALLERY / "chest.glb")
    assert r["vertices"] > 10000 and r["textures"] >= 1


def _rec():
    return {"generated_by": "test", "prompt": "a test", "seed": 1, "models": []}


def test_embed_png_roundtrip_keeps_existing_text(tmp_path, noise_png):
    from PIL import PngImagePlugin
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "from sd-cli")
    p = tmp_path / "x.png"
    Image.open(noise_png).save(p, pnginfo=info)
    side, rec = provenance.finish(p, _rec())
    assert provenance.read_embedded(p)["prompt"] == "a test"
    assert Image.open(p).text["parameters"] == "from sd-cli"
    assert json.loads(side.read_text())["output_sha256"] == provenance.registry.sha256(p)


def test_embed_wav_roundtrip(tmp_path, tone_wav):
    provenance.finish(tone_wav, _rec())
    assert provenance.read_embedded(tone_wav)["seed"] == 1
    assert checks.audio(tone_wav)["seconds"] == 1.0  # still a valid WAV
    provenance.finish(tone_wav, dict(_rec(), seed=2))  # embedding twice replaces, not appends
    assert provenance.read_embedded(tone_wav)["seed"] == 2


@pytest.mark.skipif(not lfs_present(GALLERY / "chest.glb"), reason="gallery not fetched from Git LFS")
def test_embed_glb_roundtrip(tmp_path):
    p = tmp_path / "m.glb"
    shutil.copy(GALLERY / "chest.glb", p)
    provenance.finish(p, _rec())
    assert provenance.read_embedded(p)["prompt"] == "a test"
    assert checks.mesh(p)["vertices"] > 10000  # still a valid GLB


def test_candidate_records_hold_no_absolute_paths(tmp_path, noise_png):
    from aeneas import ops
    out = tmp_path / "pick.png"

    def make_one(p, seed, i, n):
        shutil.copy(noise_png, p)
        return {"prompt": "x", "seed": seed}

    rec, listing = ops._candidates(ops.Ctx(), out, 3, 10, make_one, lambda paths: [0.1, 0.3, 0.2], "image")
    assert rec["selection"]["chosen_seed"] == 11
    assert all(c["path"].startswith("/") for c in listing)  # the caller still gets usable paths
    assert all("path" not in c and "file" in c for c in rec["selection"]["all"])  # the record keeps only portable names
