"""Recipes: several operations in a row, written as a TOML file, so a whole asset (not just one
generation) can be made again and reviewed. Recipes live in the factory's recipes/ and in
<project>/.aeneas/recipes/.

  name = "prop"
  description = "..."
  [inputs]
  subject = { help = "what the prop is" }
  size_m = { default = 1.0, help = "largest dimension in metres" }
  [[steps]]
  id = "concept"
  op = "image"
  prompt = "{subject}, a single object centred on a plain white background"
  candidates = 4
  [[steps]]
  id = "mesh"
  op = "model3d"
  src = "{concept.path}"

Placeholders: {input_name} and {step_id.field} (fields of a step's result: path, preview, ...).
Every step writes into <out_dir>/<name>/ and the run writes a manifest.json there.
"""
import datetime
import json
import re
import tomllib
from pathlib import Path

from . import ops
from .paths import ROOT, portable
from .policy import project_root

PLACEHOLDER = re.compile(r"\{([a-zA-Z_][\w]*)(?:\.([\w]+))?\}")
OUT_ARGS = {"image": ".png", "edit": ".png", "texture": ".png", "upscale": ".png", "model3d": ".glb",
            "cleanup": ".glb", "sfx": ".wav", "speech": ".wav", "matte": ".png", "comfy_image": ".png"}


class RecipeError(Exception):
    pass


def find(name, near=None):
    dirs = ([project_root(near) / ".aeneas" / "recipes"] if near else []) + [ROOT / "recipes"]
    for d in dirs:
        f = d / f"{name}.toml"
        if f.exists():
            r = tomllib.loads(f.read_text())
            r["_file"] = str(f)
            r.setdefault("name", name)
            return r
    raise RecipeError(f"no recipe named {name}")


def list_recipes(near=None):
    out = {}
    dirs = [ROOT / "recipes"] + ([project_root(near) / ".aeneas" / "recipes"] if near else [])
    for d in dirs:
        for f in sorted(d.glob("*.toml")) if d.is_dir() else []:
            r = tomllib.loads(f.read_text())
            out[f.stem] = {"description": r.get("description", ""),
                           "inputs": {k: v.get("help", "") for k, v in r.get("inputs", {}).items()}}
    return out


def validate(recipe):
    known = set(ops.OPS)
    from . import extra  # noqa: F401
    known = set(ops.OPS)
    ids = set()
    for s in recipe.get("steps", []):
        if "id" not in s or "op" not in s:
            raise RecipeError(f"{recipe['name']}: every step needs id and op")
        if s["op"] not in known:
            raise RecipeError(f"{recipe['name']}: step {s['id']} uses unknown op {s['op']}")
        for m in PLACEHOLDER.finditer(json.dumps(s)):
            name, fld = m.groups()
            if fld and name not in ids:
                raise RecipeError(f"{recipe['name']}: step {s['id']} refers to {name} before it runs")
            if not fld and name not in recipe.get("inputs", {}):
                raise RecipeError(f"{recipe['name']}: step {s['id']} uses unknown input {name}")
        ids.add(s["id"])
    return True


def _fill(value, env):
    if isinstance(value, str):
        whole = PLACEHOLDER.fullmatch(value)
        if whole:  # keep the type of a lone placeholder (numbers stay numbers)
            return _lookup(whole.groups(), env)
        return PLACEHOLDER.sub(lambda m: str(_lookup(m.groups(), env)), value)
    if isinstance(value, list):
        return [_fill(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, env) for k, v in value.items()}
    return value


def _lookup(groups, env):
    name, fld = groups
    if fld:
        res = env["steps"].get(name)
        if res is None or fld not in res:
            raise RecipeError(f"no {fld} in the result of step {name}")
        return res[fld]
    if name not in env["inputs"]:
        raise RecipeError(f"missing input {name}")
    return env["inputs"][name]


def run(name, inputs, out_dir, ctx=None, slug=None):
    out_dir = Path(out_dir).expanduser().resolve()
    recipe = find(name, near=out_dir)
    validate(recipe)
    ctx = ctx or ops.Ctx()
    vals = {}
    for k, spec in recipe.get("inputs", {}).items():
        if k in inputs:
            vals[k] = inputs[k]
        elif "default" in spec:
            vals[k] = spec["default"]
        else:
            raise RecipeError(f"recipe {name} needs input {k}: {spec.get('help', '')}")
    slug = slug or re.sub(r"[^a-z0-9]+", "-", str(vals.get(next(iter(vals), ""), name)).lower()).strip("-")[:40] or name
    folder = out_dir / slug
    folder.mkdir(parents=True, exist_ok=True)
    env = {"inputs": vals, "steps": {}}
    steps = recipe["steps"]
    manifest = {"recipe": name, "recipe_file": portable(recipe["_file"]), "inputs": vals,
                "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "steps": []}
    outer = ctx.progress
    for i, step in enumerate(steps):
        args = {k: _fill(v, env) for k, v in step.items() if k not in ("id", "op")}
        if step["op"] in ops.OPS and "out" not in args and step["op"] in OUT_ARGS:
            args["out"] = folder / f"{slug}_{step['id']}{OUT_ARGS[step['op']]}"
        ctx.progress = lambda f, msg, i=i: outer((i + f) / len(steps), f"{step['id']}: {msg}")
        outer(i / len(steps), f"step {i + 1}/{len(steps)}: {step['id']} ({step['op']})")
        res = ops.OPS[step["op"]](**args, ctx=ctx)
        env["steps"][step["id"]] = res
        manifest["steps"].append({"id": step["id"], "op": step["op"],
                                  "args": json.loads(json.dumps(args, default=str)), "result": res})
    ctx.progress = outer
    manifest["finished"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    mf = folder / "manifest.json"
    mf.write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    outer(1.0, "done")
    last = env["steps"][steps[-1]["id"]]
    return {"path": last.get("path"), "folder": str(folder), "manifest": str(mf),
            "steps": {k: {f: v for f, v in r.items() if f in ("path", "preview", "maps", "lods", "waveform")}
                      for k, r in env["steps"].items()}}
