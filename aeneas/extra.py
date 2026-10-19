"""Optional operations that need extra installs: speech (Kokoro on MLX: `make speech`), background
removal (rembg with BiRefNet: `make matte`), and images through ComfyUI (`make comfyui`).
They register themselves in ops.OPS."""
import json
import os
import shutil
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

from . import checks, ops, policy, provenance, registry
from .engines import Cancelled, EngineError
from .paths import KOKORO_PY, ROOT

VOICES = ["af_heart", "af_bella", "am_michael", "am_adam", "bf_emma", "bm_george"]


# ---------------------------------------------------------------- speech (Kokoro)

def speech(text, out, voice="af_heart", speed=1.0, ctx=None):
    ctx = ctx or ops.Ctx()
    out = ops._out(out, ".wav")
    if not KOKORO_PY.exists():
        raise EngineError("The speech environment is not set up. Run: make speech")
    registry.require("kokoro-82m")
    if voice not in VOICES:
        raise EngineError(f"voice must be one of {', '.join(VOICES)} (others: add them to models.json)")
    pol = policy.check_models(["kokoro-82m"], out)
    model_dir = registry.model_path("kokoro-82m")
    lang = voice[0]  # a: American English, b: British English
    started = provenance.datetime.datetime.now().astimezone()
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [KOKORO_PY, "-m", "mlx_audio.tts.generate", "--model", model_dir, "--text", text,
               "--voice", model_dir / "voices" / f"{voice}.safetensors", "--lang_code", lang, "--speed", str(speed),
               "--file_prefix", Path(tmp) / "speech", "--audio_format", "wav", "--join_audio"]
        ctx.progress(0.1, f"speech: {voice}")
        ctx.runner.run(cmd, out.with_name(out.name + ".log"), env={"HF_HUB_OFFLINE": "1"})
        made = sorted(Path(tmp).glob("speech*.wav"))
        if not made:
            raise EngineError("mlx-audio wrote no audio")
        shutil.move(str(made[0]), out)
    found = checks.audio(out)
    rec = provenance.record(out, "bin/ai-speech", ["kokoro-82m"], [], cmd, started, prompt=text,
                            params={"voice": voice, "speed": speed, "language": lang}, checks=found) | {"policy": pol}
    res = ops._finish(ctx, out, rec, "audio", tags=text)
    from .engines import post
    res["waveform"] = str(post.waveform_png(out, out.with_name(out.stem + "_wave.png")))
    return res


# ---------------------------------------------------------------- background removal (rembg + BiRefNet)

def matte(src, out, ctx=None):
    ctx = ctx or ops.Ctx()
    out = ops._out(out, ".png")
    registry.require("birefnet-lite")
    try:
        from PIL import Image
        os.environ["U2NET_HOME"] = str(registry.model_path("birefnet-lite"))  # rembg reads the pinned file from here
        from rembg import new_session, remove
    except ImportError:
        raise EngineError("Background removal is not installed. Run: make matte")
    pol = policy.check_models(["birefnet-lite"], out)
    started = provenance.datetime.datetime.now().astimezone()
    ctx.progress(0.2, "removing the background")
    session = new_session("birefnet-general-lite", providers=["CPUExecutionProvider"])
    with Image.open(src) as im:
        cut = remove(im.convert("RGB"), session=session)
    cut.save(out)
    alpha = cut.getchannel("A")
    kept = sum(alpha.histogram()[128:]) / (alpha.width * alpha.height)
    if kept < 0.005:
        raise checks.CheckFailed(f"{out.name}: nothing was kept (the cut-out is empty)")
    if kept > 0.995:
        raise checks.CheckFailed(f"{out.name}: nothing was removed (no background found)")
    found = {"kept_fraction": round(kept, 3), "width": cut.width, "height": cut.height}
    rec = provenance.record(out, "bin/ai-matte", ["birefnet-lite"], [], ["rembg", "birefnet-general-lite"], started,
                            inputs=[src], checks=found) | {"policy": pol}
    return ops._finish(ctx, out, rec, "image")


# ---------------------------------------------------------------- ComfyUI as an engine

COMFY_URL = os.environ.get("AEN_COMFYUI", "http://127.0.0.1:8188")
WORKFLOWS = ROOT / "aeneas" / "comfy_workflows"


def comfy_image(prompt, out, workflow="z-image-turbo", size=1024, steps=8, seed=None, ctx=None):
    """Run one of the factory's ComfyUI workflows (API format) on a running ComfyUI, same checks and
    provenance as the other engines. `make comfyui` installs it; `make comfyui-run` starts it."""
    ctx = ctx or ops.Ctx()
    out = ops._out(out, ".png")
    wf_file = WORKFLOWS / f"{workflow}.json"
    if not wf_file.exists():
        raise EngineError(f"no ComfyUI workflow {workflow} in {WORKFLOWS}")
    spec = json.loads(wf_file.read_text())
    used = spec["models"]
    for m in used:
        registry.require(m)
    pol = policy.check_models(used, out)
    seed = ops._seed(seed)
    graph = json.loads(json.dumps(spec["graph"])
                       .replace('"{prompt}"', json.dumps(prompt)).replace('"{seed}"', str(seed))
                       .replace('"{size}"', str(size)).replace('"{steps}"', str(steps)))
    started = provenance.datetime.datetime.now().astimezone()

    def call(path, body=None):
        req = urllib.request.Request(COMFY_URL + path, data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    try:
        pid = json.loads(call("/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex}))["prompt_id"]
    except urllib.error.HTTPError as e:
        raise EngineError(f"ComfyUI refused the workflow: {e.read().decode(errors='replace')[:600]}")
    except Exception as e:
        raise EngineError(f"ComfyUI is not reachable at {COMFY_URL} ({e}); start it with: make comfyui-run")
    ctx.progress(0.1, "queued in ComfyUI")
    while True:
        if ctx.cancelled():
            call("/interrupt", {})
            raise Cancelled()
        hist = json.loads(call(f"/history/{pid}")).get(pid)
        if hist:
            break
        time.sleep(1)
    status = hist.get("status", {})
    if status.get("status_str") == "error":
        raise EngineError(f"ComfyUI failed: {json.dumps(status.get('messages', []))[-600:]}")
    images = [im for node in hist["outputs"].values() for im in node.get("images", [])]
    if not images:
        raise EngineError("ComfyUI produced no image")
    im = images[0]
    q = f"/view?filename={urllib.parse.quote(im['filename'])}&subfolder={urllib.parse.quote(im['subfolder'])}&type={im['type']}"
    out.write_bytes(call(q))
    found = checks.image(out)
    rec = provenance.record(out, "comfyui", used, ["ComfyUI"], ["ComfyUI workflow", workflow], started,
                            prompt=prompt, seed=seed, params={"workflow": workflow, "size": size, "steps": steps},
                            checks=found) | {"policy": pol, "comfyui_graph": graph}
    return ops._finish(ctx, out, rec, "image", tags=prompt)


import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402

ops.OPS.update({"speech": speech, "matte": matte, "comfy_image": comfy_image})

from . import explicit_ops  # noqa: E402,F401  (diagram, svg, music, dialogue)
