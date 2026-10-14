"""Shared helpers for the bin/ commands: the model register, running a tool, and the
provenance sidecar written next to every generated file."""
import datetime
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path

# The factory's root: AEN_HOME if set, else the folder above bin/.
ROOT = Path(os.environ.get("AEN_HOME", Path(__file__).resolve().parent.parent)).expanduser().resolve()
HOME = str(Path.home())

SD_CLI = ROOT / "tools/stable-diffusion.cpp/build/bin/sd-cli"
TRELLIS_CLI = ROOT / "tools/trellis.cpp/build/trellis-cli"
MOSS_PY = ROOT / "tools/moss-soundeffect-mlx/.venv/bin/python"
MOSS_GENERATE = ROOT / "tools/moss-soundeffect-mlx/scripts/generate.py"


def register():
    return json.loads((ROOT / "models.json").read_text())


def model(model_id):
    for m in register()["models"]:
        if m["id"] == model_id:
            return m
    sys.exit(f"{model_id}: not in {ROOT / 'models.json'}")


def model_path(model_id, *parts):
    base = ROOT / model(model_id)["path"]
    return base.joinpath(*parts) if parts else base


def is_downloaded(model_id):
    m = model(model_id)
    return all((ROOT / m["path"] / f["path"]).exists() for f in m["files"])


def portable(path):
    """A path as it should appear in a record: relative to the current folder when inside it,
    else with the home folder written as ~, so a record does not name the user."""
    s = os.path.abspath(str(path))  # absolute, but symlinks (a venv's python) left as they are
    for base, prefix in ((os.path.abspath(os.getcwd()), ""), (str(ROOT), "aeneas-factory/")):
        try:
            return prefix + str(Path(s).relative_to(base))
        except ValueError:
            pass
    return "~" + s[len(HOME):] if s.startswith(HOME) else s


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def new_seed():
    return random.randint(0, 2**31 - 1)


def require_model(model_id):
    if not is_downloaded(model_id):
        sys.exit(f"{model_id} is not downloaded. Run: make models-{model(model_id)['group']}  "
                 f"(or bin/ai-models download {model_id})")


def require_tool(path, make_target):
    if not Path(path).exists():
        sys.exit(f"{portable(path)} is missing. Run: make {make_target}")


def run(cmd, log_path, env=None):
    """Run a tool, its output going to log_path; on failure show the end of the log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as log:
        log.write("$ " + " ".join(portable(c) for c in cmd) + "\n\n")
        log.flush()
        result = subprocess.run([str(c) for c in cmd], stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, **(env or {})})
    if result.returncode != 0:
        tail = log_path.read_text(errors="replace").splitlines()[-25:]
        sys.exit(f"{Path(cmd[0]).name} failed (exit {result.returncode}). End of {portable(log_path)}:\n"
                 + "\n".join(tail))


def now():
    return datetime.datetime.now().astimezone()


def write_sidecar(out, tool, model_ids, cmd, started, prompt=None, negative_prompt=None, seed=None,
                  params=None, inputs=None):
    """Write <out>.json: what made the file, from what, under which licences, and how to make it again."""
    out = Path(out)
    record = {
        "generated_by": f"aeneas-factory bin/{tool}",
        "created": started.isoformat(timespec="seconds"),
        "seconds": round((now() - started).total_seconds(), 1),
        "output": out.name,
        "output_sha256": sha256(out),
        "models": [{k: model(i).get(k) for k in ("id", "name", "upstream", "licence", "commercial_output")}
                   for i in model_ids],
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "params": {k: v for k, v in (params or {}).items() if v is not None},
        "inputs": [{"file": portable(Path(p).resolve()), "sha256": sha256(p)} for p in (inputs or [])],
        "command": [portable(c) for c in cmd],
        "machine": f"{platform.system()} {platform.machine()}",
        "note": "Made with a generative model. Credit and disclose as your project or store requires.",
    }
    side = out.with_name(out.name + ".json")
    side.write_text(json.dumps({k: v for k, v in record.items() if v not in (None, [], {})}, indent=2) + "\n")
    return side
