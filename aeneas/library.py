"""The asset library: one searchable index of everything generated and everything downloaded, with
licences and provenance. It indexes files where they are; it never moves or copies them.

Stored in ~/.aeneas/library.db (SQLite with full-text search). Image embeddings (CLIP), when the
scoring models are installed, allow searching by meaning as well as by words."""
import datetime
import json
import sqlite3
from pathlib import Path

import numpy as np

from . import policy, registry
from .paths import STATE

KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".tga": "image", ".exr": "image",
         ".hdr": "image", ".glb": "model", ".gltf": "model", ".fbx": "model", ".obj": "model", ".blend": "model",
         ".wav": "audio", ".ogg": "audio", ".mp3": "audio", ".flac": "audio", ".bvh": "motion",
         ".ttf": "font", ".otf": "font"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE, project TEXT, kind TEXT, sha256 TEXT, bytes INTEGER,
  added TEXT, origin TEXT, prompt TEXT, seed INTEGER, models TEXT, licence TEXT, source TEXT, url TEXT,
  author TEXT, tags TEXT, provenance TEXT, embedding BLOB);
CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(path, prompt, tags, source, author, licence,
  content='assets', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
  INSERT INTO assets_fts(rowid, path, prompt, tags, source, author, licence)
  VALUES (new.id, new.path, new.prompt, new.tags, new.source, new.author, new.licence); END;
CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
  INSERT INTO assets_fts(assets_fts, rowid, path, prompt, tags, source, author, licence)
  VALUES ('delete', old.id, old.path, old.prompt, old.tags, old.source, old.author, old.licence); END;
CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE ON assets BEGIN
  INSERT INTO assets_fts(assets_fts, rowid, path, prompt, tags, source, author, licence)
  VALUES ('delete', old.id, old.path, old.prompt, old.tags, old.source, old.author, old.licence);
  INSERT INTO assets_fts(rowid, path, prompt, tags, source, author, licence)
  VALUES (new.id, new.path, new.prompt, new.tags, new.source, new.author, new.licence); END;
"""


def db():
    STATE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(STATE / "library.db", timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _embed(path, kind):
    if kind != "image":
        return None
    try:
        from . import scoring
        if not scoring.available("image"):
            return None
        return scoring.image_embeddings([path])[0].astype(np.float32).tobytes()
    except Exception:
        return None


def add_generated(path, rec, tags=""):
    path = Path(path).resolve()
    kind = KINDS.get(path.suffix.lower(), "other")
    licences = sorted({l for m in rec.get("models", []) for l in registry.model(m["id"]).get("spdx", [])})
    with db() as con:
        con.execute("""INSERT INTO assets (path, project, kind, sha256, bytes, added, origin, prompt, seed, models,
            licence, source, url, author, tags, provenance, embedding) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256, bytes=excluded.bytes, added=excluded.added,
            prompt=excluded.prompt, seed=excluded.seed, models=excluded.models, licence=excluded.licence,
            tags=excluded.tags, provenance=excluded.provenance, embedding=excluded.embedding""",
                    (str(path), str(policy.project_root(path)), kind, registry.sha256(path), path.stat().st_size,
                     datetime.datetime.now().isoformat(timespec="seconds"), "generated", rec.get("prompt"),
                     rec.get("seed"), json.dumps([m["id"] for m in rec.get("models", [])]), " AND ".join(licences),
                     "aeneas-factory", None, None, tags, json.dumps(rec), _embed(path, kind)))


def import_dir(folder, source, licence, url=None, author=None, tags="", project=None, check_policy=True):
    """Index every asset file under a folder (a downloaded pack) without moving it."""
    folder = Path(folder).resolve()
    lic = policy.check_licence(licence, project or folder) if check_policy else policy.normalise(licence)
    n = 0
    with db() as con:
        for p in sorted(folder.rglob("*")):
            kind = KINDS.get(p.suffix.lower())
            if not kind or not p.is_file() or p.name.startswith("."):
                continue
            con.execute("""INSERT INTO assets (path, project, kind, sha256, bytes, added, origin, licence, source, url,
                author, tags, embedding) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET licence=excluded.licence, source=excluded.source, url=excluded.url,
                author=excluded.author, tags=excluded.tags""",
                        (str(p), str(Path(project).resolve() if project else policy.project_root(folder)), kind,
                         registry.sha256(p), p.stat().st_size, datetime.datetime.now().isoformat(timespec="seconds"),
                         "downloaded", lic, source, url, author, f"{tags} {p.stem.replace('_', ' ')}".strip(),
                         _embed(p, kind)))
            n += 1
    return n


def search(text=None, kind=None, licence=None, project=None, origin=None, limit=20):
    where, args = [], []
    for col, val in (("kind", kind), ("origin", origin)):
        if val:
            where.append(f"a.{col} = ?"); args.append(val)
    if licence:
        where.append("a.licence LIKE ?"); args.append(f"%{policy.normalise(licence)}%")
    if project:
        where.append("a.project = ?"); args.append(str(Path(project).resolve()))
    with db() as con:
        rows = []
        if text:
            terms = " OR ".join('"' + t.replace('"', "") + '"' for t in text.split() if t.strip())
            q = ("SELECT a.*, bm25(assets_fts) AS rank FROM assets_fts JOIN assets a ON a.id = assets_fts.rowid "
                 "WHERE assets_fts MATCH ?" + "".join(" AND " + w for w in where) + " ORDER BY rank LIMIT ?")
            rows = [dict(r) for r in con.execute(q, [terms, *args, limit * 3])]
            rows = _semantic(con, text, rows, where, args, limit)
        else:
            q = "SELECT a.* FROM assets a" + (" WHERE " + " AND ".join(where) if where else "") + \
                " ORDER BY a.added DESC LIMIT ?"
            rows = [dict(r) for r in con.execute(q, [*args, limit])]
    for r in rows:
        r.pop("embedding", None)
        r.pop("provenance", None)
    return rows[:limit]


def _semantic(con, text, rows, where, args, limit):
    """Blend in images whose CLIP embedding matches the text, when embeddings exist."""
    try:
        from . import scoring
        if not scoring.available("image"):
            return rows
        q = scoring.text_embeddings([text])[0]
    except Exception:
        return rows
    sql = "SELECT a.* FROM assets a WHERE a.embedding IS NOT NULL" + "".join(" AND " + w for w in where)
    cands = [dict(r) for r in con.execute(sql, args)]
    for r in cands:
        r["similarity"] = float(np.frombuffer(r["embedding"], dtype=np.float32) @ q)
    seen = {r["path"] for r in rows}
    best = sorted((r for r in cands if r["similarity"] > 0.22), key=lambda r: -r["similarity"])[:limit]
    return rows + [r for r in best if r["path"] not in seen]


def get(path):
    with db() as con:
        r = con.execute("SELECT * FROM assets WHERE path = ?", (str(Path(path).resolve()),)).fetchone()
    if not r:
        return None
    r = dict(r)
    r.pop("embedding", None)
    r["provenance"] = json.loads(r["provenance"]) if r["provenance"] else None
    return r


def credits(project):
    """A credits page for a project, from its generated and downloaded assets."""
    root = Path(project).resolve()
    with db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM assets WHERE project = ? ORDER BY origin, source, path",
                                             (str(root),))]
    lines = [f"# Credits\n", f"Generated by aeneas-factory from its asset library on "
                              f"{datetime.date.today().isoformat()}.\n"]
    downloaded = [r for r in rows if r["origin"] == "downloaded"]
    generated = [r for r in rows if r["origin"] == "generated"]
    if downloaded:
        lines.append("## Third-party assets\n")
        groups = {}
        for r in downloaded:
            groups.setdefault((r["source"], r["licence"], r["url"], r["author"]), []).append(r)
        for (source, lic, url, author), rs in groups.items():
            head = f"- **{source}**" + (f" by {author}" if author else "") + f", {lic}" + (f" ({url})" if url else "")
            lines.append(head + f": {len(rs)} file(s)")
            if lic.startswith("CC-BY"):
                lines.append("  - credit required wherever the work is shown")
    if generated:
        lines.append("\n## Generated with local models\n")
        models = {}
        for r in generated:
            for mid in json.loads(r["models"] or "[]"):
                models.setdefault(mid, []).append(Path(r["path"]).name)
        for mid, files in models.items():
            m = registry.model(mid)
            lines.append(f"- **{m['name']}** ({m['licence']}; {m['upstream']}): {len(files)} file(s), e.g. "
                         + ", ".join(sorted(files)[:5]))
        lines.append("\nEach generated file has a provenance record beside it (`<file>.json`) and inside it.")
    return "\n".join(lines) + "\n"


def remove_missing():
    with db() as con:
        gone = [r["id"] for r in con.execute("SELECT id, path FROM assets") if not Path(r["path"]).exists()]
        con.executemany("DELETE FROM assets WHERE id = ?", [(i,) for i in gone])
    return len(gone)
