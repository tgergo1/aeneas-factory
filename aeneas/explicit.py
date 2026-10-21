"""Explicit tools: code and text in, assets out. No model weights. Pixel art, music as code, sound
design, vector and procedural graphics, diagrams, CAD, mesh processing, physics, animation, levels
and dialogue. `aen tools` lists them; `aen tool NAME -- args` runs one with the right environment;
`aen tools check` proves each works by making something real.

Installed by `make explicit` (python install.py explicit): the system's package manager (Homebrew on macOS,
apt/dnf/pacman or Homebrew on Linux, winget on Windows; see deps/), Python (requirements/explicit.txt into
tools/explicit/.venv), Node (requirements/explicit-node into tools/explicit/node), .NET (Yarn Spinner into
tools/explicit/dotnet), and the GeneralUser GS SoundFont (models.json). Tools are found wherever the OS keeps
them (aeneas.host)."""
import os
import shutil
import subprocess
from pathlib import Path

from . import host
from .paths import ROOT, blender

X = ROOT / "tools" / "explicit"
PY = host.venv_python(X / ".venv")
NODE_BIN = X / "node" / "node_modules" / ".bin"
DOTNET_TOOLS = X / "dotnet"


class SandboxUnavailable(RuntimeError):
    """Code that is a program was to run sandboxed on a machine without a sandbox."""

# name: (category, how to find it, licence, what it is for)
TOOLS = {
    # images and graphics
    "magick": ("image", "path", "ImageMagick", "batch editing: resize, crop, trim, outlines, shadows, compositing, grading"),
    "python": ("code", "venv", "PSF", "the explicit-tools Python: opencv, coloraide, fonttools, music21, pretty_midi, mido, pedalboard, opensimplex, scipy, trimesh, xatlas, pymeshlab, build123d, moderngl, vtracer (image to SVG), taichi, pymunk, mujoco, tracery, manim"),
    "resvg": ("image", "path", "MPL-2.0", "SVG to PNG, exact"),
    "rsvg-convert": ("image", "path", "LGPL-2.1", "SVG to PNG or PDF (second renderer)"),
    "dot": ("diagram", "path", "EPL-1.0", "Graphviz: graphs and diagrams from text"),
    "d2": ("diagram", "path", "MPL-2.0", "diagrams from text, nicer layouts"),
    "mmdc": ("diagram", "node", "MIT", "Mermaid diagrams to SVG or PNG (headless Chrome)"),
    "vl2png": ("diagram", "node", "BSD-3-Clause", "Vega-Lite charts to PNG (also vl2svg)"),
    "vl2svg": ("diagram", "node", "BSD-3-Clause", "Vega-Lite charts to SVG"),
    # music and sound
    "fluidsynth": ("music", "path", "LGPL-2.1", "MIDI to audio with the GeneralUser GS SoundFont ($AEN_SOUNDFONT)"),
    "abc2midi": ("music", "path", "GPL-2.0", "ABC notation to MIDI"),
    "lilypond": ("music", "path", "GPL-3.0", "music notation to PDF and MIDI"),
    "csound": ("sound", "path", "LGPL-2.1", "sound design as code (.csd) rendered offline"),
    "faust": ("sound", "path", "GPL-2.0 (output is yours)", "DSP as code; faust2sndfile makes a file processor"),
    "faust2sndfile": ("sound", "path", "GPL-2.0 (output is yours)", "compile a Faust program into a sound-file processor"),
    "sclang": ("sound", "app", "GPL-3.0", "SuperCollider: synthesis and algorithmic composition; Score.recordNRT renders offline"),
    "sox": ("sound", "path", "GPL-2.0", "audio effects, conversion, synthesis of test tones"),
    "sonic-pi": ("music", "sonic-pi", "MIT (Sonic Pi; engine GPL-3.0; samples CC0; output is yours)",
                 "Sonic Pi: music as live-coded Ruby (synths, samples, FX), rendered headless to WAV, nothing played aloud: -o out.wav -d SECONDS -f song.rb [-s SEED]"),
    # 3D
    "openscad": ("3d", "app", "GPL-2.0", "solid models as code to STL, 3MF, OFF"),
    "gltfpack": ("3d", "node", "MIT", "optimise and compress glTF/GLB (meshoptimizer)"),
    "gltf-validator": ("3d", "node-script:gltf_validate.mjs", "Apache-2.0", "validate glTF/GLB files (Khronos glTF-Validator)"),
    "basisu": ("3d", "path", "Apache-2.0", "GPU texture compression to KTX2/Basis"),
    "colmap": ("3d", "path", "BSD-3-Clause", "photogrammetry: 3D from your own photos"),
    "blender": ("3d", "blender", "GPL-3.0", "modelling, QuadriFlow remeshing, Rigify rigs, BVH retargeting, bakes, renders"),
    # games, levels, dialogue
    "tiled": ("level", "app", "GPL-2.0 (maps are yours)", "tile map editor; --export-map converts maps"),
    "tmxrasterizer": ("level", "app", "GPL-2.0", "render a Tiled map to PNG"),
    "godot": ("level", "path", "MIT", "game engine; --headless for imports, exports and screenshots"),
    "inkjs-compiler": ("writing", "node", "MIT", "compile Ink branching dialogue to JSON"),
    "ysc": ("writing", "dotnet", "MIT", "Yarn Spinner: compile .yarn dialogue"),
    # motion
    "manim": ("motion", "venv-bin", "MIT", "animation as code: explainers, titles, UI motion (no LaTeX: use Text)"),
}


SONIC_PI_RECORD = ROOT / "aeneas" / "engines" / "sonicpi_record.rb"


def sonic_pi_root():
    """The folder holding Sonic Pi's etc/ and app/ (Contents/Resources in the macOS app), or None."""
    root = host.find_app("sonic-pi")
    return Path(root) if root and (Path(root) / "app" / "server" / "ruby" / "bin" / "headless_boot.rb").exists() else None


def sonic_pi():
    """Sonic Pi's own Ruby (or the system's) running the factory's recorder, or None. Needs Sonic Pi 5."""
    root = sonic_pi_root()
    if not root:
        return None
    ruby = root / "app" / "server" / "native" / "ruby" / "bin" / f"ruby{host.EXE}"
    ruby = str(ruby) if ruby.exists() else shutil.which("ruby")
    return f"{ruby}\0{SONIC_PI_RECORD}" if ruby else None


def sonic_pi_version():
    root = sonic_pi_root()
    try:
        return (root / "VERSION").read_text().strip() if root else None
    except OSError:
        return None


def soundfont():
    from . import registry
    try:
        return str(registry.model_path("generaluser-gs", "GeneralUser-GS.sf2"))
    except Exception:
        return ""


def env():
    e = dict(os.environ)
    e["PATH"] = os.pathsep.join([str(NODE_BIN), str(host.venv_python(X / ".venv").parent), str(DOTNET_TOOLS), e.get("PATH", "")])
    e["PUPPETEER_CACHE_DIR"] = str(X / "node" / ".cache" / "puppeteer")
    e["AEN_NODE_MODULES"] = str(X / "node" / "node_modules")
    for dotnet_root in ("/opt/homebrew/opt/dotnet/libexec", "/usr/local/share/dotnet", "/usr/share/dotnet", "/usr/lib/dotnet",
                        str(host.HOME / ".dotnet"), r"C:\Program Files\dotnet"):
        if Path(dotnet_root).exists():
            e.setdefault("DOTNET_ROOT", dotnet_root)
            break
    e.setdefault("DOTNET_ROLL_FORWARD", "Major")  # Yarn Spinner targets an older .NET than package managers ship
    e["AEN_SOUNDFONT"] = soundfont()
    root = sonic_pi_root()
    if root:
        e["AEN_SONIC_PI_ROOT"] = str(root)
    if host.LINUX and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        e.setdefault("QT_QPA_PLATFORM", "offscreen")  # Tiled and other Qt tools on a machine without a display
    if host.MACOS:
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
        p = host.venv_bin(X / ".venv", name)
        return str(p) if p.exists() else None
    if how == "node":
        p = NODE_BIN / (f"{name}.cmd" if host.WINDOWS else name)
        return str(p) if p.exists() else None
    if how.startswith("node-script:"):
        node, script = shutil.which("node"), ROOT / "scripts" / how.split(":", 1)[1]
        return f"{node}\0{script}" if node and script.exists() and (X / "node" / "node_modules").exists() else None
    if how == "dotnet":
        p = DOTNET_TOOLS / f"{name}{host.EXE}"
        return str(p) if p.exists() else None
    if how == "app":
        return host.find_app(name)
    if how == "sonic-pi":
        return sonic_pi()
    if how == "blender":
        return blender()
    return shutil.which(name)


def sandbox_profile(write_dir, loopback=False, readable=None):
    """The macOS profile (kept for callers and tests; see aeneas.host for every OS)."""
    return host.macos_profile(write_dir, loopback, readable)


def command(name, args, sandbox_dir=None, loopback=False, readable=None):
    """The command line for a tool. With sandbox_dir it runs in this machine's sandbox (no network, writes
    only in sandbox_dir). readable marks code that is a program (Sonic Pi, Python): it also cannot read the
    home folder, and on a machine without a sandbox it is refused unless AEN_ALLOW_UNSANDBOXED=1."""
    exe = locate(name)
    if not exe:
        raise FileNotFoundError(f"{name} is not installed; run: make explicit")
    cmd = [*exe.split("\0"), *args]  # node and ruby scripts are "interpreter\0script"
    if sandbox_dir:
        cmd, isolated = host.sandboxed(cmd, sandbox_dir, loopback, readable)
        if not isolated and readable is not None and os.environ.get("AEN_ALLOW_UNSANDBOXED") != "1":
            raise SandboxUnavailable(
                f"{name} runs code, and this machine has no sandbox for it ({host.OS}: "
                + ("install bubblewrap" if host.LINUX else "none available") + "). Set AEN_ALLOW_UNSANDBOXED=1 to run it anyway.")
    return cmd


def run(name, args, sandbox_dir=None, timeout=None, cwd=None):
    return subprocess.run(command(name, args, sandbox_dir), env=env(), cwd=cwd, timeout=timeout)


def listing():
    return [{"name": n, "category": c, "licence": lic, "purpose": what, "installed": bool(locate(n))}
            for n, (c, _, lic, what) in TOOLS.items()]
