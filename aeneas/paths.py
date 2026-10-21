"""Where things are: the factory's own folder, its tools, and the per-user state folder."""
import os
import shutil
from pathlib import Path

ROOT = Path(os.environ.get("AEN_HOME", Path(__file__).resolve().parent.parent)).expanduser().resolve()
STATE = Path(os.environ.get("AEN_STATE", Path.home() / ".aeneas")).expanduser()
HOME = str(Path.home())

from . import host

host.extend_path()  # services started at login get a minimal PATH; the tools live in the usual places

TOOLS = ROOT / "tools"
SD_CLI = host.built(TOOLS / "stable-diffusion.cpp" / "build", "sd-cli")
TRELLIS_CLI = host.built(TOOLS / "trellis.cpp" / "build", "trellis-cli")
MOSS_DIR = TOOLS / "moss-soundeffect-mlx"
MOSS_PY = host.venv_python(MOSS_DIR / ".venv")
OPENMOSS_CLI = host.built(TOOLS / "openmoss" / "build", "moss-tts-cli")
KOKORO_PY = host.venv_python(TOOLS / "kokoro" / ".venv")
COMFYUI_DIR = TOOLS / "ComfyUI"
FACTORY_PY = host.venv_python(ROOT / ".venv")

# Tool folders whose git commit goes into every provenance record.
TOOL_REPOS = {"stable-diffusion.cpp": TOOLS / "stable-diffusion.cpp", "trellis.cpp": TOOLS / "trellis.cpp",
              "moss-soundeffect-mlx": MOSS_DIR, "openmoss": TOOLS / "openmoss", "ComfyUI": COMFYUI_DIR}


def blender():
    return host.find_app("blender")


def gimp():
    return host.find_app("gimp")


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
            return prefix + Path(s).relative_to(base).as_posix()
        except ValueError:
            pass
    out = "~" + s[len(HOME):] if s.startswith(HOME) else s
    return out.replace(os.sep, "/") if os.sep != "/" else out  # records read the same on every OS
