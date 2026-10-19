"""Explicit tools: code and text in, assets out. No model weights. Pixel art, music as code, sound
design, vector and procedural graphics, diagrams, CAD, mesh processing, physics, animation, levels
and dialogue. `aen tools` lists them; `aen tool NAME -- args` runs one with the right environment;
`aen tools check` proves each works by making something real.

Installed by `make explicit`: Homebrew (Brewfile), Python (requirements/explicit.txt into
tools/explicit/.venv), Node (requirements/explicit-node into tools/explicit/node), .NET (Yarn
Spinner into tools/explicit/dotnet), and the GeneralUser GS SoundFont (models.json)."""
import os
import shutil
import subprocess
from pathlib import Path

from .paths import ROOT, blender

X = ROOT / "tools" / "explicit"
PY = X / ".venv" / "bin" / "python"
NODE_BIN = X / "node" / "node_modules" / ".bin"
DOTNET_TOOLS = X / "dotnet"
APPS = Path("/Applications")

# name: (category, how to find it, licence, what it is for)
TOOLS = {
    # images and graphics
    "magick": ("image", "brew", "ImageMagick", "batch editing: resize, crop, trim, outlines, shadows, compositing, grading"),
    "python": ("code", "venv", "PSF", "the explicit-tools Python: opencv, coloraide, fonttools, music21, pretty_midi, mido, pedalboard, opensimplex, scipy, trimesh, xatlas, pymeshlab, build123d, moderngl, vtracer (image to SVG), taichi, pymunk, mujoco, tracery, manim"),
    "resvg": ("image", "brew", "MPL-2.0", "SVG to PNG, exact"),
    "rsvg-convert": ("image", "brew", "LGPL-2.1", "SVG to PNG or PDF (second renderer)"),
    "dot": ("diagram", "brew", "EPL-1.0", "Graphviz: graphs and diagrams from text"),
    "d2": ("diagram", "brew", "MPL-2.0", "diagrams from text, nicer layouts"),
    "mmdc": ("diagram", "node", "MIT", "Mermaid diagrams to SVG or PNG (headless Chrome)"),
    "vl2png": ("diagram", "node", "BSD-3-Clause", "Vega-Lite charts to PNG (also vl2svg)"),
    "vl2svg": ("diagram", "node", "BSD-3-Clause", "Vega-Lite charts to SVG"),
    # music and sound
    "fluidsynth": ("music", "brew", "LGPL-2.1", "MIDI to audio with the GeneralUser GS SoundFont ($AEN_SOUNDFONT)"),
    "abc2midi": ("music", "brew", "GPL-2.0", "ABC notation to MIDI"),
    "lilypond": ("music", "brew", "GPL-3.0", "music notation to PDF and MIDI"),
    "csound": ("sound", "brew", "LGPL-2.1", "sound design as code (.csd) rendered offline"),
    "faust": ("sound", "brew", "GPL-2.0 (output is yours)", "DSP as code; faust2sndfile makes a file processor"),
    "faust2sndfile": ("sound", "brew", "GPL-2.0 (output is yours)", "compile a Faust program into a sound-file processor"),
    "sclang": ("sound", "app:SuperCollider.app/Contents/MacOS/sclang", "GPL-3.0", "SuperCollider: synthesis and algorithmic composition; Score.recordNRT renders offline"),
    "sox": ("sound", "brew", "GPL-2.0", "audio effects, conversion, synthesis of test tones"),
    # 3D
    "openscad": ("3d", "app:OpenSCAD.app/Contents/MacOS/OpenSCAD", "GPL-2.0", "solid models as code to STL, 3MF, OFF"),
    "gltfpack": ("3d", "node", "MIT", "optimise and compress glTF/GLB (meshoptimizer)"),
    "gltf-validator": ("3d", "node-script:gltf_validate.mjs", "Apache-2.0", "validate glTF/GLB files (Khronos glTF-Validator)"),
    "basisu": ("3d", "brew", "Apache-2.0", "GPU texture compression to KTX2/Basis"),
    "colmap": ("3d", "brew", "BSD-3-Clause", "photogrammetry: 3D from your own photos"),
    "blender": ("3d", "blender", "GPL-3.0", "modelling, QuadriFlow remeshing, Rigify rigs, BVH retargeting, bakes, renders"),
    # games, levels, dialogue
    "tiled": ("level", "app:Tiled.app/Contents/MacOS/Tiled", "GPL-2.0 (maps are yours)", "tile map editor; --export-map converts maps"),
    "tmxrasterizer": ("level", "app:Tiled.app/Contents/MacOS/tmxrasterizer", "GPL-2.0", "render a Tiled map to PNG"),
    "godot": ("level", "brew-any", "MIT", "game engine; --headless for imports, exports and screenshots"),
    "inkjs-compiler": ("writing", "node", "MIT", "compile Ink branching dialogue to JSON"),
    "ysc": ("writing", "dotnet", "MIT", "Yarn Spinner: compile .yarn dialogue"),
    # motion
    "manim": ("motion", "venv-bin", "MIT", "animation as code: explainers, titles, UI motion (no LaTeX: use Text)"),
}


def soundfont():
    from . import registry
    try:
        return str(registry.model_path("generaluser-gs", "GeneralUser-GS.sf2"))
    except Exception:
        return ""


def env():
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join([str(NODE_BIN), str(X / ".venv" / "bin"), str(DOTNET_TOOLS), e.get("PATH", "")])
    e["PUPPETEER_CACHE_DIR"] = str(X / "node" / ".cache" / "puppeteer")
    e["AEN_NODE_MODULES"] = str(X / "node" / "node_modules")
    dotnet_root = Path("/opt/homebrew/opt/dotnet/libexec")
    if dotnet_root.exists():
        e.setdefault("DOTNET_ROOT", str(dotnet_root))
    e.setdefault("DOTNET_ROLL_FORWARD", "Major")  # Yarn Spinner targets an older .NET than Homebrew's
    e["AEN_SOUNDFONT"] = soundfont()
    for var, sub in (("LIBRARY_PATH", "lib"), ("CPATH", "include")):  # faust2sndfile compiles against Homebrew libs
        e[var] = os.pathsep.join(x for x in ("/opt/homebrew/" + sub, e.get(var)) if x)
    return e


def locate(name):
    if name not in TOOLS:
        return None
    how = TOOLS[name][1]
    if how == "venv":
        return str(PY) if PY.exists() else None
    if how == "venv-bin":
        p = X / ".venv" / "bin" / name
        return str(p) if p.exists() else None
    if how == "node":
        p = NODE_BIN / name
        return str(p) if p.exists() else None
    if how.startswith("node-script:"):
        node, script = shutil.which("node"), ROOT / "scripts" / how.split(":", 1)[1]
        return f"{node}\0{script}" if node and script.exists() and (X / "node" / "node_modules").exists() else None
    if how == "dotnet":
        p = DOTNET_TOOLS / name
        return str(p) if p.exists() else None
    if how.startswith("app:"):
        p = APPS / how[4:]
        return str(p) if p.exists() else None
    if how == "blender":
        return blender()
    return shutil.which(name)


def sandbox_profile(write_dir):
    """macOS sandbox: no network, writes only inside write_dir and temporary folders."""
    w = os.path.realpath(write_dir)
    return ("(version 1)(allow default)(deny network*)(deny file-write*)"
            f'(allow file-write* (subpath "{w}") (subpath "/private/tmp") (subpath "/private/var/folders")'
            ' (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr") (literal "/dev/tty")'
            f' (subpath "{os.path.expanduser("~/Library/Caches")}"))')


def command(name, args, sandbox_dir=None):
    exe = locate(name)
    if not exe:
        raise FileNotFoundError(f"{name} is not installed; run: make explicit")
    cmd = [*exe.split("\0"), *args]  # node scripts are "node\0script"
    if sandbox_dir:
        Path(sandbox_dir).mkdir(parents=True, exist_ok=True)
        cmd = ["sandbox-exec", "-p", sandbox_profile(sandbox_dir), *cmd]
    return cmd


def run(name, args, sandbox_dir=None, timeout=None, cwd=None):
    return subprocess.run(command(name, args, sandbox_dir), env=env(), cwd=cwd, timeout=timeout)


def listing():
    return [{"name": n, "category": c, "licence": lic, "purpose": what, "installed": bool(locate(n))}
            for n, (c, _, lic, what) in TOOLS.items()]
