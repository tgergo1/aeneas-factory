"""Where things are: the factory's own folder, its tools, and the per-user state folder."""
import os
import shutil
from pathlib import Path

ROOT = Path(os.environ.get("AEN_HOME", Path(__file__).resolve().parent.parent)).expanduser().resolve()
STATE = Path(os.environ.get("AEN_STATE", Path.home() / ".aeneas")).expanduser()
HOME = str(Path.home())

# Services started by launchd (login) get a minimal PATH without Homebrew; the tools live there.
_EXTRA_PATH = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin"]
os.environ["PATH"] = os.pathsep.join(dict.fromkeys(os.environ.get("PATH", "/usr/bin:/bin").split(os.pathsep) + _EXTRA_PATH))

TOOLS = ROOT / "tools"
SD_CLI = TOOLS / "stable-diffusion.cpp/build/bin/sd-cli"
TRELLIS_CLI = TOOLS / "trellis.cpp/build/trellis-cli"
MOSS_DIR = TOOLS / "moss-soundeffect-mlx"
MOSS_PY = MOSS_DIR / ".venv/bin/python"
KOKORO_PY = TOOLS / "kokoro/.venv/bin/python"
COMFYUI_DIR = TOOLS / "ComfyUI"
FACTORY_PY = ROOT / ".venv/bin/python"

# Tool folders whose git commit goes into every provenance record.
TOOL_REPOS = {"stable-diffusion.cpp": TOOLS / "stable-diffusion.cpp", "trellis.cpp": TOOLS / "trellis.cpp",
              "moss-soundeffect-mlx": MOSS_DIR, "ComfyUI": COMFYUI_DIR}


def blender():
    for c in (os.environ.get("AEN_BLENDER"), "/Applications/Blender.app/Contents/MacOS/Blender", shutil.which("blender")):
        if c and Path(c).exists():
            return c
    return None


def gimp():
    for c in (os.environ.get("AEN_GIMP"), "/Applications/GIMP.app/Contents/MacOS/gimp-console", shutil.which("gimp-console")):
        if c and Path(c).exists():
            return c
    return None


def ffmpeg():
    return os.environ.get("AEN_FFMPEG") or shutil.which("ffmpeg")


def portable(path):
    """A path as it should appear in a record: relative to the current folder when inside it,
    `aeneas-factory/...` when inside the factory, else with the home folder as ~. Symlinks are kept."""
    if not os.path.isabs(str(path)):
        return str(path)  # already relative, or not a path at all (-Tpng, a prompt)
    s = os.path.abspath(str(path))
    cwd = os.path.abspath(os.getcwd())
    # Relative to the current folder only when that is inside home: a service started at login runs in /,
    # where "relative" would be Users/<name>/...
    bases = ([(cwd, "")] if cwd.startswith(HOME + os.sep) else []) + [(str(ROOT), "aeneas-factory/")]
    for base, prefix in bases:
        try:
            return prefix + str(Path(s).relative_to(base))
        except ValueError:
            pass
    return "~" + s[len(HOME):] if s.startswith(HOME) else s
