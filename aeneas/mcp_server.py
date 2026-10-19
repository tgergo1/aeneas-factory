"""The factory's MCP server (stdio), for Claude Code, Codex and other agents.

Each client starts its own copy; all of them send work to the one factory service, so jobs queue
instead of fighting over the GPU. Long jobs return a job id at once; job_status waits for them.
Every finished result comes back with a thumbnail the agent can look at.

No tool here runs code, downloads models or writes outside the project folder it is given."""
import datetime
import json
import re
import tempfile
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer

from . import library, provenance, service
from .engines import post

mcp = MCPServer(
    "aeneas-factory",
    instructions=(
        "Local generators for images, textures, 3D models and sound effects, with automatic checks and "
        "provenance. Always pass project_dir (the project the asset is for); outputs go to "
        "<project_dir>/generated/ unless you give a name with a folder. Look at the thumbnail of every result "
        "before using it. Long jobs (3D takes minutes) return a job_id: call job_status to wait. Use candidates "
        "(2-6) when quality matters: they are checked and ranked automatically. Before generating, "
        "search_assets may already have what you need. Respect the project's licence policy errors."),
)

EXT = {"image": ".png", "edit": ".png", "texture": ".png", "upscale": ".png", "model3d": ".glb", "sfx": ".wav",
       "speech": ".wav", "matte": ".png", "comfy_image": ".png", "diagram": ".png", "svg": ".png", "music": ".wav",
       "dialogue": ".json"}
SUBDIR = {"image": "images", "edit": "images", "texture": "textures", "upscale": "images", "model3d": "models",
          "sfx": "sounds", "speech": "speech", "matte": "images", "comfy_image": "images", "diagram": "diagrams",
          "svg": "images", "music": "music", "dialogue": "dialogue"}


def _client():
    return service.ensure_running()


def _out(op, project_dir, name, hint):
    project = Path(project_dir).expanduser()
    if not project.is_absolute():
        raise ValueError("project_dir must be an absolute path")
    stem = name or re.sub(r"[^a-z0-9]+", "-", hint.lower()).strip("-")[:40] or op
    stem += "" if name else "-" + datetime.datetime.now().strftime("%H%M%S")
    p = Path(stem)
    if not p.is_absolute():
        p = project / "generated" / SUBDIR.get(op, "other") / p
    return str(p.with_suffix(EXT.get(op, p.suffix)))


def _thumbs(result):
    """Small pictures of a result for the agent to look at."""
    out = []
    tmp = Path(tempfile.gettempdir()) / "aeneas-thumbs"
    tmp.mkdir(exist_ok=True)
    cands = [c["path"] for c in (result.get("candidates") or []) if not c.get("failed")]
    show = result.get("preview") or result.get("waveform") or (result.get("path") if str(result.get("path", "")).endswith(".png") else None)
    try:
        if show and Path(show).exists():
            out.append(Image(path=post.thumbnail(show, tmp / (Path(show).stem + "_t.png"))))
        if len(cands) > 1 and str(result.get("path", "")).endswith(".png"):
            files = [f for f in cands if Path(f).exists()]
            sheet = post.contact_sheet(files, tmp / (Path(result["path"]).stem + "_cands.png"),
                                       labels=[f"#{i + 1}" for i in range(len(files))])
            if sheet:
                out.append(Image(path=sheet))
    except Exception:
        pass
    return out


def _report(job):
    if job["status"] == "done":
        res = job["result"] or {}
        text = json.dumps({"status": "done", "job_id": job["id"], "result": res}, indent=1, default=str)
        return [text, *_thumbs(res)]
    if job["status"] in ("failed", "cancelled"):
        return json.dumps({"status": job["status"], "job_id": job["id"], "error": job["error"]})
    return json.dumps({"status": job["status"], "job_id": job["id"], "progress": job["progress"],
                       "message": job["message"], "next": "call job_status with this job_id to wait for it"})


def _submit(op, args, wait_seconds):
    c = _client()
    job = c.request("POST", "/jobs", {"kind": "op", "spec": {"op": op, "args": args}})
    if wait_seconds > 0:
        job = c.request("GET", f"/jobs/{job['id']}?wait={min(wait_seconds, 110)}", timeout=wait_seconds + 30)
    return _report(job)


@mcp.tool()
def capabilities(project_dir: str = "") -> str:
    """What the factory can make here: operations, recipes, styles, and which models are downloaded."""
    c = _client()
    caps = c.request("GET", "/capabilities" + (f"?project={project_dir}" if project_dir else ""))
    caps["models"] = c.request("GET", "/models")
    return json.dumps(caps, indent=1)


@mcp.tool()
def generate_image(prompt: str, project_dir: str, name: str = "", model: str = "", size: int = 1024,
                   seed: int | None = None, candidates: int = 1, style: str = "", negative: str = "",
                   wait_seconds: int = 60) -> list:
    """Image from text. model: z-image-turbo (default, 8 steps) or flux2-klein-4b (4 steps). candidates: make
    several, drop failures, rank by prompt match, keep the best. For a 3D source, describe one object on a plain
    white background. About 2-3 minutes per 1024 px image."""
    args = {"prompt": prompt, "out": _out("image", project_dir, name, prompt), "size": size, "seed": seed,
            "candidates": candidates, "model": model or None, "style": style or None, "negative": negative or None}
    return _submit("image", {k: v for k, v in args.items() if v is not None}, wait_seconds)


@mcp.tool()
def edit_image(instruction: str, image_path: str, project_dir: str, name: str = "", seed: int | None = None,
               candidates: int = 1, wait_seconds: int = 60) -> list:
    """Change an existing picture by instruction ("paint the door red, keep everything else"), FLUX.2 klein."""
    args = {"prompt": instruction, "src": image_path, "out": _out("edit", project_dir, name, instruction),
            "seed": seed, "candidates": candidates}
    return _submit("edit", {k: v for k, v in args.items() if v is not None}, wait_seconds)


@mcp.tool()
def make_texture(prompt: str, project_dir: str, name: str = "", size: int = 512, pbr: bool = True,
                 seed: int | None = None, candidates: int = 1, style: str = "", wait_seconds: int = 60) -> list:
    """A seamless tiling texture (seam checked), with estimated height, normal, roughness and AO maps."""
    args = {"prompt": prompt, "out": _out("texture", project_dir, name, prompt), "size": size, "pbr": pbr,
            "seed": seed, "candidates": candidates, "style": style or None}
    return _submit("texture", {k: v for k, v in args.items() if v is not None}, wait_seconds)


@mcp.tool()
def image_to_3d(image_path: str, project_dir: str, name: str = "", res: str = "512", seed: int | None = None,
                wait_seconds: int = 20) -> list:
    """Textured GLB from one image (TRELLIS.2). res 512 takes about 5 minutes, 1024 about 24. Returns a job_id;
    wait with job_status. TRELLIS.2 uses DINOv3: credit "Built with DINOv3" where the model is shipped."""
    args = {"src": image_path, "out": _out("model3d", project_dir, name, Path(image_path).stem), "res": res,
            "seed": seed}
    return _submit("model3d", {k: v for k, v in args.items() if v is not None}, wait_seconds)


@mcp.tool()
def generate_sound(prompt: str, project_dir: str, name: str = "", seconds: float = 5.0, candidates: int = 1,
                   seed: int | None = None, style: str = "", steps: int = 100, wait_seconds: int = 60) -> list:
    """Sound effect from a description (MOSS-SoundEffect, 48 kHz, up to 30 s), trimmed and loudness-normalised.
    Returns a waveform picture. About 1.5 minutes per take at 100 steps."""
    args = {"prompt": prompt, "out": _out("sfx", project_dir, name, prompt), "seconds": seconds, "seed": seed,
            "candidates": candidates, "style": style or None, "steps": steps}
    return _submit("sfx", {k: v for k, v in args.items() if v is not None}, wait_seconds)


@mcp.tool()
def upscale_image(image_path: str, project_dir: str, name: str = "", wait_seconds: int = 60) -> list:
    """Four times larger with Real-ESRGAN."""
    return _submit("upscale", {"src": image_path, "out": _out("upscale", project_dir, name,
                                                             Path(image_path).stem + "-x4")}, wait_seconds)


@mcp.tool()
def generate_speech(text: str, project_dir: str, name: str = "", voice: str = "af_heart", speed: float = 1.0,
                    wait_seconds: int = 60) -> list:
    """Spoken audio from text (Kokoro 82M). Voices: af_heart, af_bella, am_michael, bf_emma, bm_george, ..."""
    return _submit("speech", {"text": text, "voice": voice, "speed": speed,
                              "out": _out("speech", project_dir, name, text[:30])}, wait_seconds)


@mcp.tool()
def remove_background(image_path: str, project_dir: str, name: str = "", wait_seconds: int = 60) -> list:
    """Cut the subject out: a PNG with a transparent background (BiRefNet)."""
    return _submit("matte", {"src": image_path, "out": _out("matte", project_dir, name,
                                                           Path(image_path).stem + "-cutout")}, wait_seconds)


@mcp.tool()
def explicit_tools() -> str:
    """The explicit (code- and text-driven) tools installed here, beyond the generative models: image editing,
    SVG, diagrams, music and sound design as code, CAD, mesh processing, physics, animation, levels, dialogue.
    The text-based ones have their own tools here (render_diagram, render_svg, compose_music, compile_dialogue);
    the rest are run from a shell with `aen tool NAME -- args` (see the factory's AGENTS.md)."""
    from . import explicit
    return json.dumps(explicit.listing(), indent=1)


@mcp.tool()
def render_diagram(source: str, project_dir: str, kind: str = "graphviz", name: str = "", svg: bool = False,
                   wait_seconds: int = 60) -> list:
    """A diagram or chart from text. kind: graphviz (DOT), d2, mermaid, or vega-lite (a JSON spec). PNG by default,
    SVG with svg=true. The source is kept in the provenance so it can be edited and rendered again."""
    out = _out("diagram", project_dir, name, f"{kind}-diagram")
    if svg:
        out = str(Path(out).with_suffix(".svg"))
    return _submit("diagram", {"source": source, "kind": kind, "out": out}, wait_seconds)


@mcp.tool()
def render_svg(svg: str, project_dir: str, name: str = "", width: int = 0, wait_seconds: int = 60) -> list:
    """Render an SVG document you write (icons, logos, UI art, badges) to PNG with resvg; width scales it."""
    return _submit("svg", {"source": svg, "out": _out("svg", project_dir, name, "svg"), "width": width or None},
                   wait_seconds)


@mcp.tool()
def compose_music(source: str, project_dir: str, format: str = "abc", name: str = "", master: bool = True,
                  wait_seconds: int = 90) -> list:
    """Music from notation, rendered with General MIDI instruments (GeneralUser GS SoundFont), mastered to -18 LUFS.
    format "abc": ABC notation (use %%MIDI program N lines for instruments). format "notes": JSON
    {"tempo": 120, "tracks": [{"program": 0, "drums": false, "notes": [[pitch, start_beat, length_beats, velocity]]}]}.
    Returns the WAV (with a waveform picture) and the MIDI."""
    return _submit("music", {"source": source, "format": format, "master": master,
                             "out": _out("music", project_dir, name, "music")}, wait_seconds)


@mcp.tool()
def compile_dialogue(source: str, project_dir: str, kind: str = "ink", name: str = "", wait_seconds: int = 60) -> list:
    """Compile branching dialogue for a game: kind "ink" (Ink, to JSON for inkjs or ink-unity) or "yarn"
    (Yarn Spinner, to .yarnc). Compile errors come back as the error, with line numbers."""
    return _submit("dialogue", {"source": source, "kind": kind, "out": _out("dialogue", project_dir, name, kind)},
                   wait_seconds)


@mcp.tool()
def run_recipe(recipe: str, inputs: dict, project_dir: str, wait_seconds: int = 20) -> list:
    """Run a multi-step recipe (see capabilities), e.g. recipe="prop", inputs={"subject": "a wooden bucket"}.
    Results go to <project_dir>/generated/<recipe>/<slug>/ with a manifest.json."""
    c = _client()
    out_dir = str(Path(project_dir).expanduser() / "generated" / recipe)
    job = c.request("POST", "/jobs", {"kind": "recipe", "spec": {"recipe": recipe, "inputs": inputs,
                                                                 "out_dir": out_dir}})
    if wait_seconds > 0:
        job = c.request("GET", f"/jobs/{job['id']}?wait={min(wait_seconds, 110)}", timeout=wait_seconds + 30)
    return _report(job)


@mcp.tool()
def job_status(job_id: str, wait_seconds: int = 60) -> list:
    """Wait up to wait_seconds for a job, then report its progress, or its result with thumbnails."""
    job = _client().request("GET", f"/jobs/{job_id}?wait={min(wait_seconds, 110)}", timeout=wait_seconds + 30)
    return _report(job)


@mcp.tool()
def cancel_job(job_id: str) -> str:
    """Cancel a queued or running job."""
    return json.dumps(_client().request("POST", f"/jobs/{job_id}/cancel", {}))


@mcp.tool()
def list_jobs(limit: int = 10) -> str:
    """The most recent jobs and their status."""
    jobs = _client().request("GET", f"/jobs?limit={limit}")
    return json.dumps([{k: j[k] for k in ("id", "status", "progress", "message", "kind")} | {
        "what": j["spec"].get("op") or j["spec"].get("recipe")} for j in jobs], indent=1)


@mcp.tool()
def search_assets(query: str = "", project_dir: str = "", kind: str = "", licence: str = "",
                  origin: str = "", limit: int = 12) -> str:
    """Search the asset library (generated and downloaded assets) by words, and by meaning for images.
    kind: image | model | audio | font | motion. origin: generated | downloaded. licence: e.g. CC0-1.0."""
    rows = library.search(query or None, kind or None, licence or None, project_dir or None, origin or None, limit)
    return json.dumps([{k: r.get(k) for k in ("path", "kind", "origin", "licence", "source", "prompt", "author",
                                              "similarity") if r.get(k) is not None} for r in rows], indent=1)


@mcp.tool()
def get_provenance(path: str) -> str:
    """How a file was made: models, licences, prompt, seed, settings, checksums, versions."""
    rec = provenance.read_embedded(path)
    side = Path(path).with_name(Path(path).name + ".json")
    if side.exists():
        rec = json.loads(side.read_text())
    return json.dumps(rec or library.get(path) or {"error": "no provenance found"}, indent=1, default=str)


@mcp.tool()
def project_credits(project_dir: str) -> str:
    """A credits page (Markdown) for every generated and downloaded asset of a project."""
    return library.credits(project_dir)


def main():
    mcp.run("stdio")
