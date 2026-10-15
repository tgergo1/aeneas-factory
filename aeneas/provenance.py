"""Provenance: a record of how a file was made, written next to it (<file>.json) and inside it
(PNG text chunk, glTF asset.extras, WAV LIST/INFO). The record pins the factory version, every
tool's commit and every model file's checksum, so the file can be made again."""
import datetime
import functools
import json
import platform
import struct
import subprocess
from pathlib import Path

from PIL import Image, PngImagePlugin

from . import __version__, registry
from .paths import ROOT, TOOL_REPOS, portable

KEY = "aeneas:provenance"
NOTE = ("Made with generative models on this machine. The model licences are as stated on their model cards; "
        "this is not legal advice. Credit and disclose as your project or store requires.")


@functools.lru_cache(maxsize=None)
def git_commit(repo):
    repo = Path(repo)
    if not (repo / ".git").exists():
        return None
    try:
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return sha + ("+modified" if dirty else "") if sha else None
    except Exception:
        return None


def versions(tools=()):
    v = {"aeneas-factory": f"{__version__} ({git_commit(ROOT) or 'not a git checkout'})"}
    for t in tools:
        if t in TOOL_REPOS:
            v[t] = git_commit(TOOL_REPOS[t])
    return v


def model_entry(model_id):
    m = registry.model(model_id)
    return {"id": m["id"], "name": m["name"], "upstream": m["upstream"], "licence": m["licence"],
            "licence_allows_commercial_use": m["commercial_output"], "files": registry.file_record(model_id)}


def record(out, tool, model_ids, tools, cmd, started, prompt=None, negative_prompt=None, seed=None, params=None,
           inputs=None, checks=None, style=None, recipe=None):
    now = datetime.datetime.now().astimezone()
    r = {
        "generated_by": f"aeneas-factory {tool}",
        "created": started.isoformat(timespec="seconds"),
        "seconds": round((now - started).total_seconds(), 1),
        "output": Path(out).name,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "params": {k: v for k, v in (params or {}).items() if v is not None},
        "style": style,
        "recipe": recipe,
        "inputs": [{"file": portable(Path(p).resolve()), "sha256": registry.sha256(p)} for p in (inputs or [])],
        "models": [model_entry(i) for i in model_ids],
        "versions": versions(tools),
        "command": [portable(c) for c in cmd] if cmd else None,
        "checks": checks,
        "machine": f"{platform.system()} {platform.machine()}",
        "note": NOTE,
    }
    return {k: v for k, v in r.items() if v not in (None, [], {})}


# ---- embedding ----

def embed(path, rec):
    path = Path(path)
    data = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
    suffix = path.suffix.lower()
    if suffix == ".png":
        _embed_png(path, data)
    elif suffix == ".glb":
        _embed_glb(path, rec)
    elif suffix == ".wav":
        _embed_wav(path, data)
    else:
        return False
    return True


def _embed_png(path, data):
    with Image.open(path) as im:
        im.load()
        info = PngImagePlugin.PngInfo()
        for k, v in (im.text or {}).items():
            if k != KEY:
                info.add_itxt(k, v)
        info.add_itxt(KEY, data)
        im.save(path, pnginfo=info)


def _embed_glb(path, rec):
    from .checks import read_glb
    gltf, data = read_glb(path)
    json_len = struct.unpack("<I", data[12:16])[0]
    rest = data[20 + json_len:]  # the BIN chunk, if any
    gltf.setdefault("asset", {}).setdefault("extras", {})[KEY] = rec
    body = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    out = struct.pack("<I4s", len(body), b"JSON") + body + rest
    Path(path).write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(out)) + out)


def _riff_chunks(data):
    i = 12
    while i + 8 <= len(data):
        cid, size = struct.unpack("<4sI", data[i:i + 8])
        yield cid, i, size
        i += 8 + size + (size & 1)


def _embed_wav(path, data):
    raw = Path(path).read_bytes()
    keep = b"".join(raw[i:i + 8 + size + (size & 1)] for cid, i, size in _riff_chunks(raw)
                    if not (cid == b"LIST" and raw[i + 8:i + 12] == b"INFO"))
    def sub(cid, text):
        b = text.encode() + b"\0"
        return struct.pack("<4sI", cid, len(b)) + b + (b"\0" if len(b) & 1 else b"")
    info = b"INFO" + sub(b"ISFT", "aeneas-factory") + sub(b"ICMT", f"{KEY}={data}")
    lst = struct.pack("<4sI", b"LIST", len(info)) + info
    body = b"WAVE" + keep + lst
    Path(path).write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def read_embedded(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".png":
        with Image.open(path) as im:
            v = (im.text or {}).get(KEY)
        return json.loads(v) if v else None
    if suffix == ".glb":
        from .checks import read_glb
        return read_glb(path)[0].get("asset", {}).get("extras", {}).get(KEY)
    if suffix == ".wav":
        raw = path.read_bytes()
        for cid, i, size in _riff_chunks(raw):
            if cid == b"LIST" and raw[i + 8:i + 12] == b"INFO":
                j = i + 12
                while j < i + 8 + size:
                    sid, ssize = struct.unpack("<4sI", raw[j:j + 8])
                    if sid == b"ICMT":
                        text = raw[j + 8:j + 8 + ssize].rstrip(b"\0").decode()
                        if text.startswith(KEY + "="):
                            return json.loads(text[len(KEY) + 1:])
                    j += 8 + ssize + (ssize & 1)
    return None


def finish(out, rec):
    """Embed the record in the file, then write the sidecar with the final file's checksum."""
    embedded = embed(out, rec)
    side_rec = dict(rec, output_sha256=registry.sha256(out), embedded_in_file=embedded)
    side = Path(out).with_name(Path(out).name + ".json")
    side.write_text(json.dumps(side_rec, indent=2, ensure_ascii=False) + "\n")
    return side, side_rec
