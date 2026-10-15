"""Operations: what the factory can make. Each one checks the licence policy, runs an engine,
checks the result (a blank image or silent sound is a failure, not a result), writes provenance
into and beside the file, and adds it to the asset library. Optionally it makes several candidates
and ranks them. The command line, the service and the MCP server all go through here."""
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import checks, library, policy, provenance, registry, scoring, styles
from .engines import Cancelled, EngineError, Runner, moss, post, sdcpp, trellis
from .paths import portable


class OpError(Exception):
    pass


@dataclass
class Ctx:
    """What an operation needs from whoever runs it: a process runner (for cancelling) and a way to report."""
    runner: Runner = field(default_factory=Runner)
    progress: Callable[[float, str], None] = lambda f, msg: None
    add_to_library: bool = True

    def cancelled(self):
        return self.runner.cancelled


def _out(path, suffix):
    p = Path(path).expanduser().resolve()
    if p.suffix.lower() != suffix:
        p = p.with_suffix(suffix)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _seed(seed):
    return seed if seed is not None else random.randint(0, 2**31 - 1)


def _finish(ctx, out, rec, kind, tags=""):
    side, side_rec = provenance.finish(out, rec)
    if ctx.add_to_library:
        library.add_generated(out, side_rec, tags)
    return {"path": str(out), "sidecar": str(side), "kind": kind, "checks": rec.get("checks"),
            "seed": rec.get("seed"), "seconds": side_rec.get("seconds")}


def _candidates(ctx, out, n, seed, make_one, score_fn, label):
    """Make n candidates with seeds seed..seed+n-1, drop the ones that fail their checks, rank the rest
    by score_fn (higher is better), and put the best at `out`. Returns (best record, candidate list)."""
    if n <= 1:
        return make_one(out, seed, 0, 1), None
    cdir = out.with_name(out.stem + "_candidates")
    cdir.mkdir(exist_ok=True)
    made = []
    for i in range(n):
        if ctx.cancelled():
            raise Cancelled()
        p = cdir / f"{out.stem}_s{seed + i}{out.suffix}"
        try:
            rec = make_one(p, seed + i, i, n)
            made.append({"path": p, "seed": seed + i, "rec": rec})
        except checks.CheckFailed as e:
            made.append({"path": p, "seed": seed + i, "failed": str(e)})
    good = [c for c in made if "rec" in c]
    if not good:
        raise OpError(f"all {n} {label} candidates failed their checks: " + "; ".join(c["failed"] for c in made))
    try:
        scores = score_fn([c["path"] for c in good]) if score_fn and len(good) > 1 else None
    except Exception as e:  # ranking is a bonus, never a reason to fail
        scores, ctx_note = None, str(e)
    if scores:
        for c, s in zip(good, scores):
            c["score"] = round(float(s), 4)
        good.sort(key=lambda c: -c["score"])
    best = good[0]
    shutil.copy2(best["path"], out)
    listing = [{"file": portable(c["path"]), "path": str(c["path"]), "seed": c["seed"], "score": c.get("score"),
                "failed": c.get("failed")} for c in made]
    public = [{k: v for k, v in c.items() if k != "path"} for c in listing]  # records never hold absolute paths
    rec = dict(best["rec"], output=out.name,
               selection={"candidates": n, "passed_checks": len(good),
                          "ranked_by": ("CLIP" if out.suffix == ".png" else "CLAP") if scores else "first that passed",
                          "chosen_seed": best["seed"], "all": public})
    return rec, listing


# ---------------------------------------------------------------- images

def image(prompt, out, model=None, size=1024, width=None, height=None, steps=None, cfg=None, seed=None,
          negative=None, init=None, strength=0.6, refs=(), tile=False, style=None, candidates=1, gpu_vae=False,
          extra=(), ctx=None, _tool="image"):
    ctx = ctx or Ctx()
    out = _out(out, ".png")
    st = styles.find(style, near=out) if style else None
    prompt2, negative, model, style_refs, loras, lora_dir = styles.apply_image(st, prompt, negative, model)
    model = model or "z-image-turbo"
    if style_refs and model != "flux2-klein-4b" and not refs:
        model = "flux2-klein-4b"  # style references need the model that takes references
    refs = list(refs) + style_refs
    seed = _seed(seed)
    w, h = width or size, height or size
    _, used, _ = sdcpp.image_command(out, prompt2, model, w, h, steps, cfg, seed, negative, init, strength, refs,
                                     tile, loras, lora_dir, gpu_vae, extra)
    pol = policy.check_models(used, out)

    def make_one(p, s, i, n):
        cmd, used, params = sdcpp.image_command(p, prompt2, model, w, h, steps, cfg, s, negative, init, strength,
                                                refs, tile, loras, lora_dir, gpu_vae, extra)
        ctx.progress(i / n, f"image {i + 1}/{n}: {model}, seed {s}")
        started = provenance.datetime.datetime.now().astimezone()
        ctx.runner.run(cmd, p.with_name(p.name + ".log"))
        found = checks.image(p)
        if tile:
            found.update(checks.seamless(p))
        return provenance.record(p, f"bin/ai-{_tool}", used, ["stable-diffusion.cpp"], cmd, started, prompt=prompt2,
                                 negative_prompt=negative, seed=s, params=params,
                                 inputs=([init] if init else []) + refs, checks=found,
                                 style=styles.summary(st), recipe=None) | {"policy": pol}

    score = (lambda paths: scoring.image_scores(paths, prompt2)) if scoring.available("image") else None
    rec, listing = _candidates(ctx, out, candidates, seed, make_one, score, "image")
    res = _finish(ctx, out, rec, "image", tags=prompt)
    if listing:
        res["candidates"] = listing
    ctx.progress(1.0, "done")
    return res


def edit(prompt, src, out, refs=(), **kw):
    """Change an existing picture by instruction (FLUX.2 klein with the picture as reference)."""
    return image(prompt, out, model="flux2-klein-4b", refs=[src, *refs], _tool="image (edit)", **kw)


def texture(prompt, out, size=512, seed=None, style=None, candidates=1, pbr=True, ctx=None, **kw):
    """A seamless tile, its seam checked, plus estimated PBR maps and a 2x2 preview."""
    ctx = ctx or Ctx()
    res = image(prompt, out, size=size, seed=seed, style=style, candidates=candidates, tile=True, ctx=ctx,
                _tool="texture", **kw)
    out = Path(res["path"])
    res["preview"] = str(post.tile_preview(out, out.with_name(out.stem + "_2x2.png")))
    if pbr:
        res["maps"] = {k: str(v) for k, v in post.pbr_maps(out, out.parent, name=out.stem).items()}
    return res


def upscale(src, out, repeats=1, ctx=None):
    ctx = ctx or Ctx()
    out = _out(out, ".png")
    cmd, used, params = sdcpp.upscale_command(src, out, repeats)
    pol = policy.check_models(used, out)
    started = provenance.datetime.datetime.now().astimezone()
    ctx.progress(0.1, "upscaling")
    ctx.runner.run(cmd, out.with_name(out.name + ".log"))
    found = checks.image(out)
    rec = provenance.record(out, "bin/ai-upscale", used, ["stable-diffusion.cpp"], cmd, started, params=params,
                            inputs=[src], checks=found) | {"policy": pol}
    return _finish(ctx, out, rec, "image")


# ---------------------------------------------------------------- 3D

def model3d(src, out, res="512", seed=None, texture=True, bg_removal=None, preview=True, extra=(), ctx=None):
    ctx = ctx or Ctx()
    out = _out(out, ".glb")
    seed = _seed(seed)
    cmd, used, params = trellis.command(src, out, res, seed, texture, bg_removal, extra)
    pol = policy.check_models(used, out)
    checks.image(src)
    ctx.progress(0.02, f"3D at res {res}: about {trellis.MINUTES[str(res)]} minutes on an M5 Pro")
    started = provenance.datetime.datetime.now().astimezone()
    ctx.runner.run(cmd, out.with_name(out.name + ".log"))
    for f in trellis.side_files(out):
        f.unlink(missing_ok=True)
    found = checks.mesh(out)
    rec = provenance.record(out, "bin/ai-3d", used, ["trellis.cpp"], cmd, started, seed=seed, params=params,
                            inputs=[src], checks=found) | {"policy": pol}
    res_ = _finish(ctx, out, rec, "model")
    if preview:
        try:
            p = out.with_name(out.stem + "_preview.png")
            ctx.runner.run(post.preview_command(out, p), out.with_name(out.name + ".log"))
            res_["preview"] = str(p)
        except EngineError as e:
            res_["preview_error"] = str(e)
    ctx.progress(1.0, "done")
    return res_


def cleanup(src, out, size_m=1.0, faces=20000, lods=(1.0, 0.5, 0.25), ctx=None):
    """Real size, origin at the bottom centre, decimated, with LODs (Blender)."""
    ctx = ctx or Ctx()
    out = _out(out, ".glb")
    cmd = post.cleanup_command(src, out, size_m, faces, lods)
    started = provenance.datetime.datetime.now().astimezone()
    log = out.with_name(out.name + ".log")
    ctx.runner.run(cmd, log)
    info = {}
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith("AENEAS_RESULT "):
            info = __import__("json").loads(line[len("AENEAS_RESULT "):])
    found = checks.mesh(out, min_vertices=50)
    src_rec = provenance.read_embedded(src) or {}
    rec = provenance.record(out, "blender clean-up", [m["id"] for m in src_rec.get("models", [])], ["trellis.cpp"],
                            cmd, started, seed=src_rec.get("seed"), params={"size_m": size_m, "max_faces": faces,
                                                                            "lods": list(lods), **info},
                            inputs=[src], checks=found)
    res = _finish(ctx, out, rec, "model")
    res["lods"] = [str(out.with_name(l["file"])) for l in info.get("lods", [])]
    return res


# ---------------------------------------------------------------- sound

def sfx(prompt, out, seconds=5.0, steps=100, cfg=4.0, seed=None, candidates=1, master=True, style=None, ctx=None):
    ctx = ctx or Ctx()
    out = _out(out, ".wav")
    st = styles.find(style, near=out) if style else None
    prompt2 = prompt + (st.get("sfx_suffix", "") if st else "")
    seed = _seed(seed)
    pol = policy.check_models(["moss-sfx"], out)
    w = moss.worker()

    def make_one(p, s, i, n):
        ctx.progress(i / n, f"sound {i + 1}/{n}, seed {s}")
        started = provenance.datetime.datetime.now().astimezone()
        raw = p.with_name(p.stem + "_raw.wav") if master else p
        reply = w.generate(prompt2, seconds, steps, cfg, s, raw, p.with_name(p.name + ".log"), ctx.cancelled)
        params = moss.params(seconds, steps, cfg)
        if master:
            ctx.runner.run(post.loudness_command(raw, p), p.with_name(p.name + ".log"))
            raw.unlink(missing_ok=True)
            params["mastered"] = "trimmed silence, loudness -18 LUFS, peak -1 dBTP"
        found = checks.audio(p)
        return provenance.record(p, "bin/ai-sfx", ["moss-sfx"], ["moss-soundeffect-mlx"],
                                 ["moss worker", f"seed={s}"], started, prompt=prompt2, seed=s, params=params,
                                 checks=found, style=styles.summary(st)) | {"policy": pol}

    score = (lambda paths: scoring.audio_scores(paths, prompt2)) if scoring.available("audio") else None
    rec, listing = _candidates(ctx, out, candidates, seed, make_one, score, "sound")
    res = _finish(ctx, out, rec, "audio", tags=prompt)
    res["waveform"] = str(post.waveform_png(out, out.with_name(out.stem + "_wave.png")))
    if listing:
        res["candidates"] = listing
    ctx.progress(1.0, "done")
    return res


# Phase 3 operations (speech, background removal, ComfyUI) are registered by aeneas.extra.
OPS = {"image": image, "edit": edit, "texture": texture, "upscale": upscale, "model3d": model3d,
       "cleanup": cleanup, "sfx": sfx}


def run(op, args, ctx=None):
    from . import extra  # noqa: F401  (registers the optional operations)
    if op not in OPS:
        raise OpError(f"unknown operation {op}; known: {', '.join(sorted(OPS))}")
    return OPS[op](**args, ctx=ctx or Ctx())
