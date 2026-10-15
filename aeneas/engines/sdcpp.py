"""stable-diffusion.cpp (sd-cli): text to image, editing, image to image, tiles, LoRAs, upscaling."""
from pathlib import Path

from .. import registry
from ..paths import SD_CLI
from . import EngineError

TEXT_ENCODER = ("z-image-turbo", "Qwen3-4B-Instruct-2507-Q8_0.gguf")
IMAGE_MODELS = {
    # model id: (sd-cli model arguments, default steps, default cfg, models used)
    "z-image-turbo": (lambda: ["--diffusion-model", registry.model_path("z-image-turbo", "z_image_turbo-Q8_0.gguf"),
                               "--llm", registry.model_path(*TEXT_ENCODER),
                               "--vae", registry.model_path("z-image-turbo", "ae.safetensors")],
                      8, 1.0, ["z-image-turbo"]),
    "flux2-klein-4b": (lambda: ["--diffusion-model", registry.model_path("flux2-klein-4b", "flux-2-klein-4b-Q8_0.gguf"),
                                "--llm", registry.model_path(*TEXT_ENCODER),
                                "--vae", registry.model_path("flux2-klein-4b", "flux2_vae.safetensors")],
                       4, 1.0, ["flux2-klein-4b", "z-image-turbo"]),
}


def require_tool():
    if not SD_CLI.exists():
        raise EngineError("sd-cli is not built. Run: make sd")


def image_command(out, prompt, model="z-image-turbo", width=1024, height=1024, steps=None, cfg=None, seed=0,
                  negative=None, init=None, strength=0.6, refs=(), tile=False, loras=(), lora_dir=None,
                  gpu_vae=False, extra=()):
    """Returns (command, models used, effective params)."""
    if model not in IMAGE_MODELS:
        raise EngineError(f"unknown image model {model}; choose from {', '.join(IMAGE_MODELS)}")
    args, d_steps, d_cfg, used = IMAGE_MODELS[model]
    for m in used:
        registry.require(m)
    require_tool()
    steps = steps or d_steps
    cfg = d_cfg if cfg is None else cfg
    for name, weight in loras:
        prompt += f"<lora:{name}:{weight}>"
    cmd = [SD_CLI, *args(), "-p", prompt, "--cfg-scale", str(cfg), "--steps", str(steps), "-W", str(width),
           "-H", str(height), "--seed", str(seed), "-o", Path(out)]
    if negative:
        cmd += ["-n", negative]
    if init:
        cmd += ["-i", Path(init).resolve(), "--strength", str(strength)]
    for r in refs:
        cmd += ["-r", Path(r).resolve()]
    if tile:
        cmd += ["--circular"]
    if loras:
        cmd += ["--lora-model-dir", Path(lora_dir)]
    if not gpu_vae:
        # The Metal VAE decode gives a blank image with this build (checked 2026-10-15); the CPU decode is right.
        cmd += ["--backend", "vae=cpu"]
    cmd += list(extra)
    params = {"model": model, "width": width, "height": height, "steps": steps, "cfg": cfg,
              "strength": strength if init else None, "tile": tile or None,
              "loras": [f"{n}:{w}" for n, w in loras] or None}
    return cmd, used, params


def upscale_command(src, out, repeats=1):
    registry.require("realesrgan-x4plus")
    require_tool()
    cmd = [SD_CLI, "-M", "upscale", "--upscale-model", registry.model_path("realesrgan-x4plus", "RealESRGAN_x4plus.pth"),
           "--upscale-repeats", str(repeats), "-i", Path(src).resolve(), "-o", Path(out)]
    return cmd, ["realesrgan-x4plus"], {"scale": 4 ** repeats}
