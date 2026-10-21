#!/usr/bin/env python3
"""Aeneas Factory installer for macOS, Linux and Windows: builds the tools, sets up the Python environments,
downloads the models and checks that everything works. Everything lands inside this folder (.venv/, tools/,
models/). Python 3.10 or later; nothing but the standard library.

  python install.py help                       the steps
  python install.py install --groups image     prereqs, environment, tools, image models, a quick check

On Linux and macOS `make <step>` runs the same steps (GROUPS=, ACCEPT=, AEN_GPU=, CMAKE_ARGS= work as before).
On Windows use `py install.py <step>` from a "Developer PowerShell for VS" (for the C++ builds)."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from aeneas import host  # noqa: E402  (standard library only)

# Pinned upstream sources: the exact commits this repository was tested with.
PINS = {
    "sd": ("https://github.com/leejet/stable-diffusion.cpp", "59c23bce0d82be3a922023ab811194f05b3e2faa", "stable-diffusion.cpp"),
    "trellis": ("https://github.com/pwilkin/trellis.cpp", "2516c48b677050c570f47eba2e68dc8a5bc918b0", "trellis.cpp"),
    "moss-mlx": ("https://github.com/xocialize/moss-soundeffect-mlx.git", "4e8e3e36d4d9c991d16a3e65a4b7099d406b9ed8", "moss-soundeffect-mlx"),
    "openmoss": ("https://github.com/pwilkin/openmoss", "bfb1f465e0a86fb5a52bbf93e67ceba4b7d0b4e1", "openmoss"),  # v0.3.0
    "comfyui": ("https://github.com/Comfy-Org/ComfyUI.git", "3541246a9c997f4b8c32f9f88f3c985d02021c79", "ComfyUI"),  # v0.40.0
    "comfyui-gguf": ("https://github.com/city96/ComfyUI-GGUF.git", "6ea2651e7df66d7585f6ffee804b20e92fb38b8a", "ComfyUI/custom_nodes/ComfyUI-GGUF"),
}
YARN_SPINNER = "3.2.2"
TOOLS = ROOT / "tools"
VENV = ROOT / ".venv"
PY = host.venv_python(VENV)

STEPS = {}


def step(help_text):
    def wrap(fn):
        STEPS[fn.__name__.replace("_", "-")] = (fn, help_text)
        return fn
    return wrap


def run(cmd, cwd=None, env=None, check=True):
    cmd = [str(c) for c in cmd]
    print("+", subprocess.list2cmdline(cmd) if host.WINDOWS else " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    if check and r.returncode != 0:
        sys.exit(f"failed (exit {r.returncode}): {cmd[0]}")
    return r.returncode


def aen(*args):
    if not PY.exists():
        factory(A)
    return run([PY, "-m", "aeneas", *args], cwd=ROOT)


def uv():
    u = shutil.which("uv")
    if not u:
        sys.exit("uv is needed: https://docs.astral.sh/uv/getting-started/installation/ "
                 "(macOS: brew install uv; Linux: your package manager or pipx install uv; Windows: winget install astral-sh.uv)")
    return u


def venv(path, seed=False):
    run([uv(), "venv", "--quiet", "--allow-existing", *(["--seed"] if seed else []), "--python", A.python, path])
    return host.venv_python(path)


def pip(py, *args, env=None):
    run([uv(), "pip", "install", "--quiet", "--python", py, *args], env={"UV_HTTP_TIMEOUT": "180", **(env or {})})


def checkout(key):
    url, commit, rel = PINS[key]
    d = TOOLS / rel
    if not (d / ".git").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", url, d])
    run(["git", "-C", d, "fetch", "--quiet", "origin", commit], check=False)
    run(["git", "-C", d, "checkout", "--quiet", commit])
    run(["git", "-C", d, "submodule", "update", "--init", "--recursive", "--quiet"])
    return d


def stamp(name):
    return TOOLS / f".{name}"


def built_already(name, legacy):
    """Up to date: this stamp, or the Makefile's older one (Metal builds before the backend was in the name)."""
    return stamp(name).exists() or (host.APPLE_SILICON and (TOOLS / legacy).exists())


def done(name):
    for old in TOOLS.glob(f".{name.split('-')[0]}-*"):
        old.unlink()
    stamp(name).touch()


# ---------------------------------------------------------------- C++ builds with the right GPU backend

BACKEND_FLAGS = {  # stable-diffusion.cpp has its own names; trellis.cpp and openmoss take ggml's
    "sd": {"metal": ["-DSD_METAL=ON"], "cuda": ["-DSD_CUDA=ON"], "vulkan": ["-DSD_VULKAN=ON"], "cpu": []},
    "ggml": {"metal": [], "cuda": ["-DGGML_CUDA=ON"], "vulkan": ["-DGGML_VULKAN=ON"], "cpu": []},
}


def cmake_build(src, target, flags):
    build = src / "build"
    gen = ["-G", "Ninja"] if host.WINDOWS and shutil.which("ninja") else []
    extra = A.cmake_args.split() if A.cmake_args else []
    win = ["-DGGML_OPENMP=OFF"] if host.WINDOWS else []
    run(["cmake", "-S", src, "-B", build, *gen, "-DCMAKE_BUILD_TYPE=Release", *flags, *win, *extra])
    run(["cmake", "--build", build, "--config", "Release", "--target", target, "-j", str(A.jobs)])


def gpu_note():
    g = host.gpu()
    print(f"GPU backend: {g}" + ("" if g != "cpu" else " (no GPU toolkit found: CUDA needs nvcc, Vulkan needs glslc and "
                                  "the Vulkan SDK; set AEN_GPU=cuda|vulkan to choose. On the CPU images are slow and 3D takes hours.)"))
    return g


# ---------------------------------------------------------------- steps

@step("Everything for --groups (default all): prereqs, environment, tools, models, quick check")
def install(a):
    prereqs(a)
    factory(a)
    tools(a)
    models(a)
    check_quick(a)


@step("Check that the build prerequisites are installed")
def prereqs(a):
    ok = True
    print(f"machine: {host.OS} {host.ARCH}, Python {sys.version.split()[0]}, sandbox: {host.sandbox_kind() or 'none'}")
    gpu_note()
    for c in ("git", "cmake", "uv", "curl"):
        if not shutil.which(c):
            print(f"MISS  {c}: {hint(c)}")
            ok = False
    compiler = {"macos": "clang++", "linux": "c++", "windows": "cl"}[host.OS]
    if not shutil.which(compiler):
        print(f"MISS  a C++ compiler ({compiler}): {hint('compiler')}")
        ok = False
    if not shutil.which("ffmpeg"):
        print(f"INFO  ffmpeg not found: sound mastering needs it ({hint('ffmpeg')})")
    if not host.find_app("blender"):
        print("INFO  Blender not found: 3D previews and clean-up need it (https://www.blender.org/download/)")
    if host.LINUX and not host.sandbox_kind():
        print("INFO  bubblewrap (bwrap) not found or not allowed: explicit tools run unsandboxed and code (Sonic Pi) is refused")
    if host.WINDOWS:
        print("INFO  Windows has no sandbox for the explicit tools: notation renders run unsandboxed, code (Sonic Pi) is refused")
    free = shutil.disk_usage(ROOT).free // 10**9
    if free < 20:
        print(f"WARN  {free} GB free here; images need about 17 GB, everything about 45 GB")
    if not ok:
        sys.exit("install the missing tools above, then run this again")
    print(f"prerequisites ok ({free} GB free)")


def hint(tool):
    return {
        "macos": {"compiler": "xcode-select --install", "default": f"brew install {tool}"},
        "linux": {"compiler": "sudo apt install build-essential (or your distribution's compiler package)",
                  "uv": "pipx install uv, or https://docs.astral.sh/uv/", "default": f"sudo apt install {tool} (or dnf/pacman)"},
        "windows": {"compiler": "Visual Studio Build Tools with C++ (winget install Microsoft.VisualStudio.2022.BuildTools), "
                                "then run from a Developer PowerShell",
                    "git": "winget install Git.Git", "cmake": "winget install Kitware.CMake", "uv": "winget install astral-sh.uv",
                    "ffmpeg": "winget install Gyan.FFmpeg", "default": f"winget search {tool}"},
    }[host.OS].get(tool) or {"macos": f"brew install {tool}", "linux": f"sudo apt install {tool}", "windows": f"winget search {tool}"}[host.OS]


@step("The factory's own Python environment (commands, service, MCP server)")
def factory(a):
    py = venv(VENV)
    pip(py, "--require-hashes", "-r", ROOT / "requirements" / "factory.txt")
    # make `python -m aeneas` work from any folder (login items, the Windows Run entry)
    site = Path(subprocess.check_output([str(py), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], text=True).strip())
    (site / "aeneas-factory.pth").write_text(str(ROOT) + "\n")
    print(f"factory environment ready: {py}")


@step("Build the core tools: stable-diffusion.cpp, trellis.cpp, and the sound engine")
def tools(a):
    sd(a)
    trellis(a)
    moss(a)


@step("Build stable-diffusion.cpp (sd-cli) for this machine's GPU (Metal, CUDA, Vulkan or CPU)")
def sd(a):
    g = gpu_note()
    name = f"sd-{PINS['sd'][1][:12]}-{g}"
    if built_already(name, f".sd-{PINS['sd'][1]}"):
        print("sd-cli is up to date")
        return
    src = checkout("sd")
    cmake_build(src, "sd-cli", BACKEND_FLAGS["sd"][g])
    done(name)


@step("Build trellis.cpp (trellis-cli) for this machine's GPU; on the CPU it works but takes hours per model")
def trellis(a):
    g = gpu_note()
    name = f"trellis-{PINS['trellis'][1][:12]}-{g}"
    if built_already(name, f".trellis-{PINS['trellis'][1]}"):
        print("trellis-cli is up to date")
        return
    src = checkout("trellis")
    cmake_build(src, "trellis-cli", BACKEND_FLAGS["ggml"][g])
    done(name)


@step("The sound engine: MLX on Apple Silicon, openmoss (moss-tts-cli, CUDA/Vulkan/CPU) elsewhere")
def moss(a):
    if host.APPLE_SILICON and os.environ.get("AEN_SOUND", "mlx") == "mlx":
        name = f"moss-{PINS['moss-mlx'][1][:12]}"
        if built_already(name, f".moss-{PINS['moss-mlx'][1]}"):
            print("MOSS (MLX) environment is up to date")
            return
        src = checkout("moss-mlx")
        py = venv(src / ".venv", seed=True)
        pip(py, "-r", ROOT / "requirements" / "moss-sfx.txt")
        pip(py, "--no-deps", "-e", src)
        done(name)
        return
    g = gpu_note()
    name = f"openmoss-{PINS['openmoss'][1][:12]}-{g}"
    if stamp(name).exists():
        print("moss-tts-cli is up to date")
        return
    src = checkout("openmoss")
    cmake_build(src, "moss-tts-cli", BACKEND_FLAGS["ggml"][g])
    done(name)


@step("Optional: rank candidates by prompt match (torch, transformers); then: models --groups scoring")
def scoring(a):
    factory_ready()
    pip(PY, "--require-hashes", "-r", ROOT / "requirements" / "scoring.txt")


@step("Optional: background removal (rembg, onnxruntime); then: models --groups matte")
def matte(a):
    factory_ready()
    pip(PY, "--require-hashes", "-r", ROOT / "requirements" / "matte.txt")


@step("Optional: text to speech (Kokoro: MLX on Apple Silicon, PyTorch elsewhere); then: models --groups speech")
def speech(a):
    py = venv(TOOLS / "kokoro" / ".venv")
    lock = "speech.txt" if host.APPLE_SILICON else "speech-torch.txt"
    pip(py, "--require-hashes", "-r", ROOT / "requirements" / lock)


@step("All optional environments: scoring, matte, speech")
def extras(a):
    scoring(a)
    matte(a)
    speech(a)


def factory_ready():
    if not PY.exists():
        factory(A)


# ---------------------------------------------------------------- explicit tools

def linux_package_manager():
    for pm in ("apt-get", "dnf", "pacman", "zypper"):
        if shutil.which(pm):
            return pm
    return "brew" if shutil.which("brew") else None


def deps(name):
    """Package names from deps/NAME.txt (one per line, # comments)."""
    out = []
    for line in (ROOT / "deps" / f"{name}.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


@step("Explicit tools: code and text in, assets out (system packages, Python, Node, .NET, SoundFont; no model weights)")
def explicit(a):
    factory_ready()
    system_packages(a)
    py = venv(TOOLS / "explicit" / ".venv")
    pip(py, "--require-hashes", "-r", ROOT / "requirements" / "explicit.txt")
    node = TOOLS / "explicit" / "node"
    node.mkdir(parents=True, exist_ok=True)
    for f in ("package.json", "package-lock.json"):
        shutil.copy(ROOT / "requirements" / "explicit-node" / f, node / f)
    npm = shutil.which("npm")
    if npm:
        run([npm, "ci", "--no-audit", "--no-fund"], cwd=node, env={"PUPPETEER_CACHE_DIR": str(node / ".cache" / "puppeteer")})
    else:
        print("SKIP  Node tools (Mermaid, Vega-Lite, Ink, gltfpack): install Node.js 20 or later")
    dotnet = shutil.which("dotnet")
    if dotnet and not (TOOLS / "explicit" / "dotnet" / f"ysc{host.EXE}").exists():
        run([dotnet, "tool", "install", "YarnSpinner.Console", "--version", YARN_SPINNER, "--tool-path", TOOLS / "explicit" / "dotnet"])
    elif not dotnet:
        print("SKIP  Yarn Spinner: install the .NET SDK 8 or later")
    aen("models", "download", "generaluser-gs")
    run([PY, "-m", "aeneas", "tools", "check"], cwd=ROOT, check=False)


def system_packages(a):
    """Install the explicit tools' system packages where that needs no password (Homebrew, winget); print the
    command where it does (apt, dnf, pacman), or run it with --system."""
    if host.MACOS:
        if not shutil.which("brew"):
            sys.exit("Homebrew is needed on macOS: https://brew.sh")
        run(["brew", "bundle", "--file", ROOT / "Brewfile", "--no-upgrade"])
        return
    if host.WINDOWS:
        if not shutil.which("winget"):
            print("SKIP  system packages: winget is not available; install the tools listed in deps/winget.txt by hand")
            return
        for pkg in deps("winget"):
            run(["winget", "install", "--id", pkg, "--exact", "--silent", "--accept-source-agreements",
                 "--accept-package-agreements", "--disable-interactivity"], check=False)
        print("INFO  not on winget (install by hand if you need them): resvg, rsvg-convert, FluidSynth, abcMIDI, Csound, "
              "Faust, basisu, COLMAP. See README: Explicit tools on Windows.")
        return
    pm = linux_package_manager()
    if pm is None:
        print("SKIP  system packages: no known package manager; install the tools in deps/apt.txt by hand")
        return
    names = deps({"apt-get": "apt", "dnf": "dnf", "pacman": "pacman", "zypper": "dnf", "brew": "brew-linux"}[pm])
    base = {"apt-get": ["sudo", "apt-get", "install", "-y", "--no-install-recommends"], "dnf": ["sudo", "dnf", "install", "-y"],
            "pacman": ["sudo", "pacman", "-S", "--needed", "--noconfirm"], "zypper": ["sudo", "zypper", "install", "-y"],
            "brew": ["brew", "install"]}[pm]
    # apt's list is verified, so one command; the others go one by one so an unknown name only skips itself
    cmds = [base + names] if pm == "apt-get" else [base + [n] for n in names]
    if pm == "brew" or a.system:
        for cmd in cmds:
            run(cmd, check=False)
    else:
        print("Install the system packages with (needs your password; or run this step with --system):")
        for cmd in cmds[:1] if pm == "apt-get" else [base + names]:
            print("  " + " ".join(cmd))
    print("Tools that are missing are reported by `aen tools check` and are simply unavailable; deps/"
          + {"apt-get": "apt", "dnf": "dnf", "pacman": "pacman", "zypper": "dnf", "brew": "brew-linux"}[pm]
          + ".txt says where to get the ones your distribution does not package.")


# ---------------------------------------------------------------- ComfyUI

@step("Optional: ComfyUI as an engine and a UI, sharing models/ (about 2 GB)")
def comfyui(a):
    factory_ready()
    src = checkout("comfyui")
    checkout("comfyui-gguf")
    py = venv(src / ".venv")
    pip(py, "-r", src / "requirements.txt", "-r", src / "custom_nodes" / "ComfyUI-GGUF" / "requirements.txt")
    link = src / "custom_nodes" / "aeneas_nodes"
    target = ROOT / "comfy_nodes" / "aeneas_nodes"
    if link.is_symlink() or link.exists():
        shutil.rmtree(link) if link.is_dir() and not link.is_symlink() else link.unlink()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:  # Windows without developer mode cannot make symlinks: copy instead
        shutil.copytree(target, link)
    yaml = subprocess.check_output([str(PY), str(ROOT / "scripts" / "comfyui_paths.py")], text=True)
    (src / "extra_model_paths.yaml").write_text(yaml)


@step("Start ComfyUI on 127.0.0.1:8188 (UI and engine for comfy_image)")
def comfyui_run(a):
    src = TOOLS / "ComfyUI"
    run([host.venv_python(src / ".venv"), "main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch"], cwd=src)


# ---------------------------------------------------------------- models, checks, service

def _accept():
    return [x for k in (A.accept or "").replace(",", " ").split() for x in ("--accept", k)]


@step("Download the models for --groups (default all core models; add --accept dinov3 for 3D)")
def models(a):
    aen("models", "download", *(a.groups.split() or ["all"]), *_accept())


for _g, _what in [("image", "Image models: Z-Image Turbo, FLUX.2 klein (15.7 GB)"),
                  ("3d", "TRELLIS.2 (16.5 GB); needs --accept dinov3 after reading the DINOv3 licence"),
                  ("sound", "MOSS-SoundEffect (8.4 GB on Apple Silicon, 7.1 GB elsewhere)"),
                  ("scoring", "SigLIP and CLAP for ranking candidates (1.4 GB)"), ("upscale", "Real-ESRGAN x4 (67 MB)"),
                  ("matte", "BiRefNet lite for background removal (224 MB)"), ("speech", "Kokoro 82M with six voices (330 MB)")]:
    def _models(a, g=_g):
        aen("models", "download", g, *_accept())
    _models.__name__ = f"models_{_g}"
    step(_what)(_models)


@step("All optional models (2.1 GB)")
def models_extras(a):
    aen("models", "download", "scoring", "upscale", "matte", "speech")


@step("Health check with a tiny job through every installed generator (minutes)")
def check(a):
    aen("check")


@step("Health check without the generation jobs (seconds)")
def check_quick(a):
    aen("check", "--quick")


@step("Check the SHA-256 of every downloaded model file")
def verify(a):
    aen("models", "verify", "--full")


@step("List the models and whether they are downloaded")
def list(a):  # noqa: A001
    aen("models", "list")


@step("Run the test suite (no models or GPU needed)")
def test(a):
    factory_ready()
    run([PY, "-m", "pytest", "-q", "tests"], cwd=ROOT)


@step("Start the factory service (the MCP server also starts it on demand)")
def service_start(a):
    aen("service", "start")


@step("Stop the factory service")
def service_stop(a):
    aen("service", "stop")


@step("Start the factory service at login (LaunchAgent, systemd user unit, or Windows Run entry)")
def autostart(a):
    aen("service", "autostart", "on")


@step("Stop starting the service at login")
def autostart_off(a):
    aen("service", "autostart", "off")


@step("Show how to register the MCP server with Claude Code and Codex")
def mcp_info(a):
    launcher = ROOT / "bin" / ("aen.cmd" if host.WINDOWS else "aen")
    print(f"Claude Code:  claude mcp add --scope user aeneas -- {launcher} mcp")
    print(f"Codex:        codex mcp add aeneas -- {launcher} mcp")


# ---------------------------------------------------------------- the editor extension

def _npm(*args):
    npm = shutil.which("npm") or sys.exit("Node.js 20 or later is needed for the editor extension")
    run([npm, *args], cwd=ROOT / "editors" / "vscode")


@step("Build the VS Code extension (editors/vscode/aeneas-factory.vsix); needs Node")
def vscode(a):
    _npm("ci", "--ignore-scripts", "--no-audit", "--no-fund")
    _npm("run", "package")


@step("Build the extension and install it (--vscode-cli cursor for Cursor)")
def vscode_install(a):
    vscode(a)
    cli = a.vscode_cli or shutil.which("code") or {
        "macos": "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
        "windows": str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd"),
        "linux": "code"}[host.OS]
    run([cli, "--install-extension", ROOT / "editors" / "vscode" / "aeneas-factory.vsix", "--force"])


@step("Test the extension: unit tests, then integration tests in a real VS Code against the running service")
def vscode_test(a):
    _npm("ci", "--ignore-scripts", "--no-audit", "--no-fund")
    _npm("test")


# ---------------------------------------------------------------- cleaning

@step("Remove the tool builds and environments (keeps sources and models)")
def clean_tools(a):
    for p in ["stable-diffusion.cpp/build", "trellis.cpp/build", "openmoss/build", "moss-soundeffect-mlx/.venv", "kokoro/.venv"]:
        shutil.rmtree(TOOLS / p, ignore_errors=True)
    for s in TOOLS.glob(".*-*"):
        s.unlink()


@step("Remove tools/ and .venv entirely (keeps models/)")
def distclean(a):
    shutil.rmtree(TOOLS, ignore_errors=True)
    shutil.rmtree(VENV, ignore_errors=True)


@step("Show this list")
def help(a):  # noqa: A001
    print(f"Aeneas Factory installer ({host.OS} {host.ARCH}, GPU backend {host.gpu()}).\n")
    for name, (_, text) in STEPS.items():
        print(f"  {name:16} {text}")
    print("\nStart with:  python install.py install --groups image   (images only, 15.7 GB)"
          "\n             python install.py install --accept dinov3   (everything, about 40 GB)")


def main(argv=None):
    global A
    ap = argparse.ArgumentParser(prog="install.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("steps", nargs="*", default=["help"], help="one or more steps; `help` lists them")
    ap.add_argument("--groups", default=os.environ.get("GROUPS", "all"), help="models to download: all, groups or ids")
    ap.add_argument("--accept", default=os.environ.get("ACCEPT", ""), help="licences you accept, e.g. dinov3")
    ap.add_argument("--python", default=os.environ.get("PYTHON_VERSION", "3.12"), help="Python version for the environments")
    ap.add_argument("--cmake-args", default=os.environ.get("CMAKE_ARGS", ""), help="extra CMake flags for the C++ builds")
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS") or host.jobs()))
    ap.add_argument("--gpu", choices=["metal", "cuda", "vulkan", "cpu"], help="override the detected GPU backend")
    ap.add_argument("--system", action="store_true", help="explicit: also install system packages with sudo (Linux)")
    ap.add_argument("--vscode-cli", default=os.environ.get("VSCODE_CLI"), help="the editor's command (code, cursor, ...)")
    A = ap.parse_args(argv)
    if A.gpu:
        os.environ["AEN_GPU"] = A.gpu
    for s in A.steps:
        if s not in STEPS:
            sys.exit(f"unknown step {s}; run: python install.py help")
        STEPS[s][0](A)


A = None
if __name__ == "__main__":
    main()
