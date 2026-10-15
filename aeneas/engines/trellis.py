"""trellis.cpp (trellis-cli): one image to a textured GLB with TRELLIS.2."""
from pathlib import Path

from .. import registry
from ..paths import TRELLIS_CLI
from . import EngineError

# Measured on an M5 Pro: res 512 about 5 minutes, res 1024 about 24 minutes.
MINUTES = {"512": 5, "1024": 24, "1536": 45}


def command(image, out, res="512", seed=0, texture=True, bg_removal=None, extra=()):
    if not TRELLIS_CLI.exists():
        raise EngineError("trellis-cli is not built. Run: make trellis")
    registry.require("trellis2")
    res = str(res)
    if res not in MINUTES:
        raise EngineError(f"res must be one of {', '.join(MINUTES)}")
    cmd = [TRELLIS_CLI, "--image", Path(image).resolve(), "--output", Path(out), "--models",
           registry.model_path("trellis2"), "--res", res, "--seed", str(seed)]
    if not texture:
        cmd += ["--no-texture"]
    if bg_removal:
        cmd += ["--bg-removal", bg_removal]
    cmd += list(extra)
    return cmd, ["trellis2"], {"res": res, "texture": texture, "bg_removal": bg_removal or "auto"}


def side_files(out):
    """trellis.cpp leaves <name>.ply and <name>_base.png beside the GLB."""
    out = Path(out)
    return [out.with_suffix(".ply"), out.with_name(out.stem + "_base.png")]
