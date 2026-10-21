"""Post-processing without models: Blender clean-up and previews, audio loudness and trimming,
PBR maps from a texture, waveform pictures, thumbnails."""
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..paths import ROOT, blender, ffmpeg
from . import EngineError

SCRIPTS = ROOT / "scripts"


# ---- Blender ----

def blender_command(script, *args):
    b = blender()
    if not b:
        raise EngineError("Blender is needed for this step: install it from https://www.blender.org (or set AEN_BLENDER to its path)")
    return [b, "-b", "--factory-startup", "--python", SCRIPTS / script, "--", *map(str, args)]


def cleanup_command(src, out, size_m=1.0, faces=20000, lods=(1.0, 0.5, 0.25)):
    """Scale to a real size, put the origin at the bottom centre, decimate, export LODs."""
    return blender_command("blender_cleanup.py", Path(src).resolve(), Path(out).resolve(), size_m, faces,
                           ",".join(str(x) for x in lods))


def preview_command(src, out, size=768):
    return blender_command("render_glb.py", Path(src).resolve(), Path(out).resolve(), size)


# ---- audio ----

def loudness_command(src, out, lufs=-18.0, peak=-1.0, trim=True):
    f = ffmpeg()
    if not f:
        raise EngineError("ffmpeg is needed for this step (brew install ffmpeg)")
    chain = []
    if trim:
        # Trim leading and trailing silence below -50 dB.
        chain.append("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
                     "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse")
    chain.append(f"loudnorm=I={lufs}:TP={peak}:LRA=11")
    return [f, "-y", "-loglevel", "error", "-i", Path(src).resolve(), "-af", ",".join(chain), "-ar", "48000",
            "-c:a", "pcm_s16le", Path(out).resolve()]


def waveform_png(wav, out, width=1200, height=200, colour=(13, 148, 136)):
    import wave
    with wave.open(str(wav), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels()).mean(axis=1)
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cols = np.array_split(np.abs(x), width) if x.size else []
    peak = max(float(np.abs(x).max()) if x.size else 0.0, 1e-6)
    for i, c in enumerate(cols):
        v = np.sqrt(float(c.max()) / peak) if c.size else 0.0  # square-root scale: quiet parts stay visible
        h = max(1, int(v * (height / 2 - 2)))
        d.line([(i, height / 2 - h), (i, height / 2 + h)], fill=colour + (255,))
    im.save(out)
    return out


# ---- textures ----

def pbr_maps(albedo, out_dir, strength=2.0, name=None):
    """Height, normal (OpenGL convention, tiling), roughness and AO maps estimated from a colour texture.
    They are estimates from brightness, good for prototypes; a scanned or hand-made set is better."""
    albedo = Path(albedo)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = name or albedo.stem
    with Image.open(albedo) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    # Height: brightness with fine noise removed and the broad shading taken out (wrapping, so it tiles).
    def blur(a, r):
        k = Image.fromarray((a * 255).astype(np.uint8))
        big = Image.new("L", (k.width * 3, k.height * 3))
        for i in range(3):
            for j in range(3):
                big.paste(k, (i * k.width, j * k.height))
        big = big.filter(ImageFilter.GaussianBlur(r))
        return np.asarray(big.crop((k.width, k.height, 2 * k.width, 2 * k.height)), dtype=np.float32) / 255.0
    height = blur(lum, 1.0) - blur(lum, max(lum.shape) / 16) + 0.5
    height = (height - height.min()) / max(float(np.ptp(height)), 1e-6)
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    n = np.stack([-dx, dy, np.ones_like(height)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    normal = ((n * 0.5 + 0.5) * 255).astype(np.uint8)
    rough = np.clip(0.55 + 0.4 * (1 - height) - 0.2 * (lum - lum.mean()), 0, 1)
    ao = np.clip(1 - (blur(height, max(lum.shape) / 64) - height) * 2.5, 0, 1)
    files = {}
    for kind, arr in (("height", height), ("roughness", rough), ("ao", ao)):
        p = out_dir / f"{stem}_{kind}.png"
        Image.fromarray((arr * 255).astype(np.uint8), "L").save(p)
        files[kind] = p
    p = out_dir / f"{stem}_normal.png"
    Image.fromarray(normal, "RGB").save(p)
    files["normal"] = p
    return files


def tile_preview(src, out, n=2):
    with Image.open(src) as im:
        im = im.convert("RGB")
        big = Image.new("RGB", (im.width * n, im.height * n))
        for i in range(n):
            for j in range(n):
                big.paste(im, (i * im.width, j * im.height))
        big.save(out)
    return out


def thumbnail(src, out, size=384):
    with Image.open(src) as im:
        im = im.convert("RGBA")
        im.thumbnail((size, size))
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        bg.convert("RGB").save(out)
    return out


def contact_sheet(images, out, size=256, labels=None):
    ims = []
    for p in images:
        with Image.open(p) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            ims.append(im.copy())
    if not ims:
        return None
    sheet = Image.new("RGB", (size * len(ims), size + (20 if labels else 0)), "white")
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        sheet.paste(im, (i * size + (size - im.width) // 2, (size - im.height) // 2))
        if labels:
            d.text((i * size + 6, size + 4), str(labels[i]), fill="black")
    sheet.save(out)
    return out


def copy(src, dst):
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst
