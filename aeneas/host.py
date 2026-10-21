"""The machine the factory runs on: which OS and GPU, where Python environments keep their interpreter, where
desktop apps are installed, and how to start a program sandboxed. Everything that differs between macOS, Linux
and Windows is decided here, so the rest of the factory does not test for the OS itself."""
import glob
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

OS = "macos" if sys.platform == "darwin" else "windows" if sys.platform.startswith("win") else "linux"
MACOS, LINUX, WINDOWS = OS == "macos", OS == "linux", OS == "windows"
ARCH = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
APPLE_SILICON = MACOS and ARCH == "arm64"
EXE = ".exe" if WINDOWS else ""
HOME = Path.home()


def venv_python(venv):
    """The interpreter of a virtual environment (bin/python, or Scripts\\python.exe on Windows)."""
    venv = Path(venv)
    return venv / "Scripts" / "python.exe" if WINDOWS else venv / "bin" / "python"


def venv_bin(venv, name):
    """A console script installed into a virtual environment."""
    venv = Path(venv)
    return venv / "Scripts" / f"{name}.exe" if WINDOWS else venv / "bin" / name


def built(build_dir, name):
    """A program built with CMake: build/bin/NAME, or build/bin/Release/NAME.exe with Visual Studio."""
    build_dir = Path(build_dir)
    options = [build_dir / "bin" / f"{name}{EXE}", build_dir / "bin" / "Release" / f"{name}{EXE}",
               build_dir / f"{name}{EXE}", build_dir / "Release" / f"{name}{EXE}"]
    return next((p for p in options if p.exists()), options[0])


def jobs():
    return os.cpu_count() or 4


# ---------------------------------------------------------------- the search path

# Services started at login (launchd, systemd, Task Scheduler) get a minimal PATH; tools live in these.
EXTRA_PATH = {
    "macos": ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin"],
    "linux": [str(HOME / ".local" / "bin"), "/home/linuxbrew/.linuxbrew/bin", "/usr/local/bin", "/snap/bin",
              "/var/lib/flatpak/exports/bin", str(HOME / ".local" / "share" / "flatpak" / "exports" / "bin")],
    "windows": [str(Path(os.environ.get("LOCALAPPDATA", HOME)) / "Microsoft" / "WinGet" / "Links"),
                str(HOME / "scoop" / "shims"), r"C:\ProgramData\chocolatey\bin"],
}[OS]


def extend_path():
    parts = os.environ.get("PATH", "/usr/bin:/bin" if not WINDOWS else "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys([p for p in parts if p] + EXTRA_PATH))


# ---------------------------------------------------------------- desktop apps

def _program_files():
    return [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA") if os.environ.get(v)]


def _win(*patterns):
    return [str(Path(base) / p) for base in _program_files() for p in patterns]


# Where each app is usually installed, per OS; PATH names are tried after these. AEN_<NAME> overrides all.
APPS = {
    "blender": {"macos": ["/Applications/Blender.app/Contents/MacOS/Blender"],
                "linux": ["/opt/blender/blender", str(HOME / "blender" / "blender")],
                "windows": _win("Blender Foundation/Blender */blender.exe"),
                "names": ["blender"]},
    "gimp": {"macos": ["/Applications/GIMP.app/Contents/MacOS/gimp-console"],
             "linux": [], "windows": _win("GIMP 3/bin/gimp-console-*.exe", "GIMP 2/bin/gimp-console-*.exe"),
             "names": ["gimp-console", "gimp-console-3.0", "gimp-console-2.10"]},
    "gimp-app": {"macos": ["/Applications/GIMP.app"], "linux": [],
                 "windows": _win("GIMP 3/bin/gimp-*.exe", "GIMP 2/bin/gimp-*.exe"), "names": ["gimp"]},
    "godot": {"macos": ["/Applications/Godot.app/Contents/MacOS/Godot", "/Applications/Godot_mono.app/Contents/MacOS/Godot"],
              "linux": [], "windows": _win("Godot*/Godot*.exe"), "names": ["godot", "godot4"]},
    "sclang": {"macos": ["/Applications/SuperCollider.app/Contents/MacOS/sclang"], "linux": [],
               "windows": _win("SuperCollider*/sclang.exe"), "names": ["sclang"]},
    "openscad": {"macos": ["/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"], "linux": [],
                 "windows": _win("OpenSCAD*/openscad.com", "OpenSCAD*/openscad.exe"), "names": ["openscad"]},
    "tiled": {"macos": ["/Applications/Tiled.app/Contents/MacOS/Tiled"], "linux": [],
              "windows": _win("Tiled/tiled.exe"), "names": ["tiled"]},
    "tmxrasterizer": {"macos": ["/Applications/Tiled.app/Contents/MacOS/tmxrasterizer"], "linux": [],
                      "windows": _win("Tiled/tmxrasterizer.exe"), "names": ["tmxrasterizer"]},
    # Sonic Pi: the folder holding its etc/ and app/ (Contents/Resources inside the macOS app bundle)
    "sonic-pi": {"macos": ["/Applications/Sonic Pi.app/Contents/Resources"],
                 "linux": ["/opt/sonic-pi", "/usr/lib/sonic-pi", "/usr/share/sonic-pi", str(HOME / "sonic-pi")],
                 "windows": _win("Sonic Pi"), "names": []},
}


def find_app(name):
    """The path of an installed app or program, or None. AEN_BLENDER, AEN_GIMP, ... override the search."""
    env = os.environ.get("AEN_" + name.upper().replace("-", "_"))
    if env and Path(env).exists():
        return env
    spec = APPS.get(name, {"names": [name]})
    for pattern in spec.get(OS, []):
        hits = sorted(glob.glob(os.path.expanduser(pattern)), reverse=True)  # the newest version first
        if hits:
            return hits[0]
    for n in spec.get("names", []):
        hit = shutil.which(n)
        if hit:
            return hit
    return None


# ---------------------------------------------------------------- the GPU

def gpu():
    """The compute backend to build and run with: metal, cuda, vulkan or cpu. AEN_GPU overrides."""
    choice = os.environ.get("AEN_GPU", "").lower()
    if choice in ("metal", "cuda", "vulkan", "cpu"):
        return choice
    if APPLE_SILICON:
        return "metal"
    if shutil.which("nvidia-smi") and (shutil.which("nvcc") or os.environ.get("CUDA_PATH")):
        return "cuda"
    if shutil.which("glslc") and (shutil.which("vulkaninfo") or os.environ.get("VULKAN_SDK")):
        return "vulkan"
    return "cpu"


def torch_index():
    """The PyTorch wheel index for this machine's GPU (None: the default index, CPU or Apple's MPS)."""
    if MACOS:
        return None
    if shutil.which("nvidia-smi"):
        return "https://download.pytorch.org/whl/cu128"
    return "https://download.pytorch.org/whl/cpu"


# ---------------------------------------------------------------- sandboxing

def sandbox_kind():
    """How this machine isolates programs: sandbox-exec (macOS), bwrap (Linux, bubblewrap), or None."""
    if os.environ.get("AEN_NO_SANDBOX") == "1":
        return None
    if MACOS and shutil.which("sandbox-exec"):
        return "sandbox-exec"
    if LINUX and shutil.which("bwrap") and _bwrap_works():
        return "bwrap"
    return None


_BWRAP_OK = None


def _bwrap_works():
    """bwrap is installed but some systems forbid unprivileged user namespaces; try it once."""
    global _BWRAP_OK
    if _BWRAP_OK is None:
        try:
            _BWRAP_OK = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--unshare-net", "true"],
                                       capture_output=True, timeout=10).returncode == 0
        except Exception:
            _BWRAP_OK = False
    return _BWRAP_OK


def _caches():
    if MACOS:
        return HOME / "Library" / "Caches"
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local")) / "Temp"
    return Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache"))


def macos_profile(write_dir, loopback=False, readable=None):
    """sandbox-exec profile: no network, writes only inside write_dir and temporary folders.
    loopback: also allow network on this machine's loopback (programs made of local parts that talk over it,
    like Sonic Pi). readable: when given, nothing under the home folder can be read except write_dir and these
    paths (for code that is a program, not notation: it cannot read the service token, keys or documents)."""
    w = os.path.realpath(write_dir)
    home = os.path.realpath(str(HOME))
    net = "(deny network*)"
    if loopback:
        net += ('(allow network-bind network-inbound (local ip "localhost:*"))'
                '(allow network-outbound (remote ip "localhost:*"))')
    reads = ""
    if readable is not None:
        allowed = " ".join(f'(subpath "{os.path.realpath(r)}")' for r in [w, *readable])
        reads = f'(deny file-read-data (subpath "{home}"))(allow file-read-data {allowed})'
    return ("(version 1)(allow default)" + net + "(deny file-write*)"
            f'(allow file-write* (subpath "{w}") (subpath "/private/tmp") (subpath "/private/var/folders")'
            ' (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr") (literal "/dev/tty")'
            f' (subpath "{home}/Library/Caches"))' + reads)


def bwrap_args(write_dir, loopback=False, readable=None):
    """bubblewrap: the whole system read-only, a private /tmp, writes only inside write_dir (and the user's
    cache folder), no network (a private network namespace has only its own loopback, which is all that
    loopback programs need). readable: the home folder is replaced by an empty one except write_dir and
    these paths."""
    w = os.path.realpath(write_dir)
    args = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
            "--unshare-net", "--unshare-pid", "--unshare-ipc", "--die-with-parent", "--new-session"]
    cache = _caches()
    if readable is not None:
        args += ["--tmpfs", str(HOME)]
        for r in readable:
            r = os.path.realpath(r)
            if os.path.exists(r):
                args += ["--ro-bind", r, r]
    elif cache.is_dir():
        args += ["--bind", str(cache), str(cache)]
    for d in ("/run/user/%d" % os.getuid(),) if hasattr(os, "getuid") else ():
        if os.path.isdir(d) and loopback:  # sound servers (PipeWire, PulseAudio) for programs that open an audio device
            args += ["--bind", d, d]
    args += ["--bind", w, w, "--chdir", w, "--"]
    return args


def sandboxed(cmd, write_dir, loopback=False, readable=None):
    """cmd wrapped in this machine's sandbox, and whether it is isolated at all."""
    kind = sandbox_kind()
    Path(write_dir).mkdir(parents=True, exist_ok=True)
    if kind == "sandbox-exec":
        return ["sandbox-exec", "-p", macos_profile(write_dir, loopback, readable), *cmd], True
    if kind == "bwrap":
        return [*bwrap_args(write_dir, loopback, readable), *cmd], True
    return list(cmd), False


# ---------------------------------------------------------------- opening things for people

def open_file(path, app=None):
    """Open a file or folder in its default app (or a given app) without waiting for it."""
    path = str(path)
    if MACOS:
        cmd = ["open", "-a", app, path] if app else ["open", path]
    elif WINDOWS:
        if app:
            cmd = [app, path]
        else:
            os.startfile(path)  # noqa: S606  (Windows only)
            return
    else:
        cmd = [app, path] if app else ["xdg-open", path]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def summary():
    return {"os": OS, "arch": ARCH, "gpu": gpu(), "sandbox": sandbox_kind() or "none", "python": sys.version.split()[0]}
