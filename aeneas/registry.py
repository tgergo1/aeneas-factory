"""The model register (models.json): every model file, pinned URL, size, SHA-256 and licence.
Downloading, verifying, and the explicit licence acceptance some models need."""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import ROOT, STATE


class RegistryError(Exception):
    pass


def load():
    return json.loads((ROOT / "models.json").read_text())


def models():
    return load()["models"]


def model(model_id):
    for m in models():
        if m["id"] == model_id:
            return m
    raise RegistryError(f"{model_id}: not in models.json")


def model_path(model_id, *parts):
    base = ROOT / model(model_id)["path"]
    return base.joinpath(*parts) if parts else base


def is_downloaded(model_id):
    m = model(model_id)
    return all((ROOT / m["path"] / f["path"]).exists() for f in m["files"])


def require(model_id):
    if not is_downloaded(model_id):
        m = model(model_id)
        raise RegistryError(f"{model_id} is not downloaded. Run: make models-{m['group']}  (or aen models download {model_id})")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def file_state(m, f, full=False):
    p = ROOT / m["path"] / f["path"]
    if not p.exists():
        return "missing"
    if p.stat().st_size != f["bytes"]:
        return "wrong size"
    if full and sha256(p) != f["sha256"]:
        return "wrong sha256"
    return "ok"


def selection(names):
    """Expand names (all, a group, or model ids) into model ids, requirements first."""
    groups = {m["group"] for m in models()}
    ids = []
    for n in names:
        if n == "all":
            ids += [m["id"] for m in models() if m.get("default", True)]
        elif n in groups:
            ids += [m["id"] for m in models() if m["group"] == n]
        else:
            ids.append(model(n)["id"])
    out = []
    for i in ids:
        for r in model(i).get("requires", []) + [i]:
            if r not in out:
                out.append(r)
    return out


# ---- licence acceptance (models whose licence asks for explicit agreement) ----

def _accepted_file():
    return STATE / "accepted.json"


def accepted():
    try:
        return json.loads(_accepted_file().read_text())
    except FileNotFoundError:
        return {}


def accept(key, licence, url):
    STATE.mkdir(parents=True, exist_ok=True)
    a = accepted()
    a[key] = {"licence": licence, "url": url, "accepted": datetime.date.today().isoformat()}
    _accepted_file().write_text(json.dumps(a, indent=2) + "\n")


def needs_acceptance(model_id):
    """[(key, licence, url, files)] still to accept before this model may be downloaded."""
    out = []
    env = {k.strip() for k in os.environ.get("AEN_ACCEPT", "").split(",") if k.strip()}
    for acc in model(model_id).get("accept", []):
        if acc["key"] not in accepted() and acc["key"] not in env:
            out.append(acc)
    return out


# ---- download and verify ----

def gb(n):
    return f"{n / 1e9:.1f} GB"


def download(names, force=False, accept_keys=(), log=print):
    ids = selection(names)
    for i in ids:
        for acc in needs_acceptance(i):
            if acc["key"] in accept_keys:
                accept(acc["key"], acc["licence"], acc["url"])
                log(f"accepted {acc['licence']} ({acc['url']}) for {', '.join(acc['files'])}")
            else:
                raise RegistryError(
                    f"{i} includes {', '.join(acc['files'])}, which is under the {acc['licence']}: {acc['url']}\n"
                    f"{acc['why']}\nRead it, then download with --accept {acc['key']} "
                    f"(make: ACCEPT={acc['key']}), or skip this model.")
    todo = [(model(i), f) for i in ids for f in model(i)["files"] if file_state(model(i), f) != "ok"]
    need = sum(f["bytes"] for _, f in todo)
    log(f"{len(ids)} model(s): {', '.join(ids)}; {len(todo)} file(s) to fetch, {gb(need)}")
    if not todo:
        return
    (ROOT / "models").mkdir(exist_ok=True)
    free = shutil.disk_usage(ROOT / "models").free
    if need > free - 2e9 and not force:
        raise RegistryError(f"Only {gb(free)} free on this disk; {gb(need)} is needed. Free space or pass --force.")
    if not shutil.which("curl"):
        raise RegistryError("curl is needed to download.")
    for m, f in todo:
        dest = ROOT / m["path"] / f["path"]
        part = dest.with_name(dest.name + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        log(f"\n{m['id']}: {f['path']} ({gb(f['bytes'])})")
        if not (part.exists() and part.stat().st_size == f["bytes"]):  # a finished .part needs no request
            r = subprocess.run(["curl", "-L", "--fail", "--retry", "5", "--retry-delay", "5", "-C", "-",
                                "--progress-bar", "-o", str(part), f["url"]])
            if r.returncode != 0 and not (part.exists() and part.stat().st_size == f["bytes"]):
                raise RegistryError(f"download failed (curl exit {r.returncode}); run the same command again to resume")
        got = sha256(part)
        if got != f["sha256"]:
            part.unlink()
            raise RegistryError(f"checksum mismatch for {f['path']}: expected {f['sha256']}, got {got}. "
                                "The partial file was removed.")
        os.replace(part, dest)
        log("  sha256 ok")
    log("\ndone")


def verify(ids=(), full=False):
    """[(model_id, state, detail)] with state ok | missing-all | problem."""
    out = []
    for m in models():
        if ids and m["id"] not in ids:
            continue
        states = [(f, file_state(m, f, full)) for f in m["files"]]
        problems = [(f, s) for f, s in states if s != "ok"]
        if problems and all(s == "missing" for _, s in problems) and len(problems) == len(states):
            out.append((m["id"], "not downloaded", ""))
        elif problems:
            out += [(m["id"], "problem", f"{f['path']} {s}") for f, s in problems]
        else:
            out.append((m["id"], "ok", f"{len(states)} files, {'sha256' if full else 'sizes'}"))
    return out


def file_record(model_id):
    """What a provenance record needs to pin a model: its files with their checksums and URLs."""
    m = model(model_id)
    return [{"file": f["path"], "sha256": f["sha256"], "url": f["url"]} for f in m["files"]]


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
