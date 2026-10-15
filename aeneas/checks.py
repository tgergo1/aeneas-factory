"""Automatic checks on generated files. A file that fails is not a result: a blank image,
silent audio or a mesh with nothing in it must never be reported as a success."""
import json
import struct
import wave
from pathlib import Path

import numpy as np
from PIL import Image


class CheckFailed(Exception):
    pass


def image(path, min_std=4.0, min_size=16):
    """A real picture: decodes, has size, and is not (near) one flat colour."""
    try:
        with Image.open(path) as im:
            im.load()
            rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    except Exception as e:
        raise CheckFailed(f"{Path(path).name}: not a readable image ({e})")
    h, w = rgb.shape[:2]
    if h < min_size or w < min_size:
        raise CheckFailed(f"{Path(path).name}: only {w}x{h} pixels")
    std = float(rgb.std(axis=(0, 1)).mean())
    if std < min_std:
        raise CheckFailed(f"{Path(path).name}: the image is blank (one flat colour, spread {std:.1f}); "
                          "nothing was drawn")
    return {"width": w, "height": h, "spread": round(std, 1)}


def seamless(path, max_ratio=1.6):
    """A tile's edges should continue into each other about as smoothly as neighbouring pixels inside it."""
    with Image.open(path) as im:
        a = np.asarray(im.convert("L"), dtype=np.float32)
    inner = (np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean()) / 2
    wrap = (np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0, :] - a[-1, :]).mean()) / 2
    ratio = float(wrap / max(inner, 1e-6))
    if ratio > max_ratio:
        raise CheckFailed(f"{Path(path).name}: visible seam (edge jump {ratio:.2f}x the texture's own detail)")
    return {"seam_ratio": round(ratio, 2)}


def audio(path, min_rms_db=-60.0, min_seconds=0.1):
    """Real sound: decodes, has length, and is not silent."""
    try:
        with wave.open(str(path), "rb") as w:
            n, ch, sw, rate = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(n)
    except Exception as e:
        raise CheckFailed(f"{Path(path).name}: not a readable WAV ({e})")
    if sw != 2:
        raise CheckFailed(f"{Path(path).name}: expected 16-bit audio, got {sw * 8}-bit")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    seconds = n / rate if rate else 0
    if seconds < min_seconds:
        raise CheckFailed(f"{Path(path).name}: only {seconds:.2f} s long")
    rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    rms_db = float(20 * np.log10(max(rms, 1e-9)))
    if rms_db < min_rms_db:
        raise CheckFailed(f"{Path(path).name}: silent (level {rms_db:.0f} dBFS)")
    peak_db = float(20 * np.log10(max(float(np.abs(x).max()), 1e-9)))
    return {"seconds": round(seconds, 2), "rms_dbfs": round(rms_db, 1), "peak_dbfs": round(peak_db, 1),
            "sample_rate": rate, "channels": ch}


def read_glb(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack("<4sII", data[:12])
    if magic != b"glTF":
        raise CheckFailed(f"{Path(path).name}: not a GLB file")
    n, kind = struct.unpack("<I4s", data[12:20])
    if kind != b"JSON":
        raise CheckFailed(f"{Path(path).name}: GLB without a JSON chunk")
    return json.loads(data[20:20 + n]), data


def mesh(path, min_vertices=500, min_extent=1e-4):
    """A real model: has geometry with some volume, and textures when it should."""
    try:
        gltf, _ = read_glb(path)
    except CheckFailed:
        raise
    except Exception as e:
        raise CheckFailed(f"{Path(path).name}: unreadable GLB ({e})")
    verts, lo, hi = 0, [], []
    for m in gltf.get("meshes", []):
        for p in m.get("primitives", []):
            acc = gltf["accessors"][p["attributes"]["POSITION"]]
            verts += acc["count"]
            if "min" in acc and "max" in acc:
                lo.append(acc["min"]); hi.append(acc["max"])
    if verts < min_vertices:
        raise CheckFailed(f"{Path(path).name}: only {verts} vertices")
    extent = None
    if lo:
        mn, mx = np.min(np.array(lo), axis=0), np.max(np.array(hi), axis=0)
        extent = [round(float(v), 4) for v in (mx - mn)]
        if min(extent) < min_extent:
            raise CheckFailed(f"{Path(path).name}: flat in one direction (extent {extent})")
    return {"vertices": verts, "extent": extent, "textures": len(gltf.get("images", [])),
            "materials": len(gltf.get("materials", []))}


def check(path, kind=None, **kw):
    kind = kind or {".png": "image", ".jpg": "image", ".webp": "image", ".wav": "audio", ".glb": "mesh"}.get(
        Path(path).suffix.lower())
    if kind == "image":
        return image(path, **kw)
    if kind == "audio":
        return audio(path, **kw)
    if kind == "mesh":
        return mesh(path, **kw)
    raise CheckFailed(f"no check for {Path(path).name}")
