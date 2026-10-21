"""`aen`: the factory's command line. When the factory service is running, generation jobs go
through its queue (so nothing fights over the GPU); --local runs them in this process instead."""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import __version__, library, ops, policy, recipes, registry, service, styles
from .paths import ROOT, blender, ffmpeg, gimp, portable


def _p(s):
    return str(Path(s).expanduser().resolve())


def _run_op(a, op, args):
    """Run an operation through the service when it is up (unless --local), else here."""
    args = {k: v for k, v in args.items() if v is not None}
    client = None if a.local else service.running()
    if client:
        job = client.request("POST", "/jobs", {"kind": "op", "spec": {"op": op, "args": args}})
        return _follow(client, job)
    last = [""]

    def progress(f, msg):
        if msg != last[0]:
            print(f"  [{f:4.0%}] {msg}", file=sys.stderr, flush=True)
            last[0] = msg
    return ops.run(op, args, ops.Ctx(progress=progress))


def _follow(client, job):
    print(f"job {job['id']} queued in the factory service", file=sys.stderr)
    last = ""
    try:
        while job["status"] in ("queued", "running"):
            job = client.request("GET", f"/jobs/{job['id']}?wait=5", timeout=40)
            line = f"  [{job['progress']:4.0%}] {job['message']}"
            if line != last:
                print(line, file=sys.stderr, flush=True)
                last = line
    except KeyboardInterrupt:
        client.request("POST", f"/jobs/{job['id']}/cancel", {})
        sys.exit("cancelled")
    if job["status"] != "done":
        sys.exit(f"{job['status']}: {job.get('error')}")
    return job["result"]


def _print(res):
    print(json.dumps(res, indent=2, default=str))


def _gen_args(p, candidates=True):
    p.add_argument("--seed", type=int)
    if candidates:
        p.add_argument("--candidates", type=int, default=1, help="make several, keep the best that passes its checks")
    p.add_argument("--style", help="a style pack (aen style list)")
    p.add_argument("--local", action="store_true", help="run here, not through the factory service")


def cmd_image(a):
    _print(_run_op(a, "image", dict(prompt=a.prompt, out=_p(a.out), model=a.model, size=a.size, width=a.width,
                                    height=a.height, steps=a.steps, cfg=a.cfg, seed=a.seed, negative=a.neg,
                                    init=_p(a.init) if a.init else None, strength=a.strength,
                                    refs=[_p(r) for r in a.ref], tile=a.tile, style=a.style,
                                    candidates=a.candidates, gpu_vae=a.gpu_vae, extra=a.extra)))


def cmd_edit(a):
    _print(_run_op(a, "edit", dict(prompt=a.instruction, src=_p(a.src), out=_p(a.out), seed=a.seed,
                                   candidates=a.candidates, style=a.style, refs=[_p(r) for r in a.ref])))


def cmd_texture(a):
    _print(_run_op(a, "texture", dict(prompt=a.prompt, out=_p(a.out), size=a.size, seed=a.seed, style=a.style,
                                      candidates=a.candidates, pbr=not a.no_pbr)))


def cmd_3d(a):
    _print(_run_op(a, "model3d", dict(src=_p(a.image), out=_p(a.out), res=a.res, seed=a.seed,
                                      texture=not a.no_texture, bg_removal=a.bg_removal, preview=not a.no_preview,
                                      extra=a.extra)))


def cmd_cleanup(a):
    _print(_run_op(a, "cleanup", dict(src=_p(a.mesh), out=_p(a.out), size_m=a.size_m, faces=a.faces,
                                      lods=[float(x) for x in a.lods.split(",")])))


def cmd_sfx(a):
    _print(_run_op(a, "sfx", dict(prompt=a.prompt, out=_p(a.out), seconds=a.seconds, steps=a.steps, cfg=a.cfg,
                                  seed=a.seed, candidates=a.candidates, master=not a.raw, style=a.style)))


def cmd_speech(a):
    _print(_run_op(a, "speech", dict(text=a.text, out=_p(a.out), voice=a.voice, speed=a.speed)))


def cmd_upscale(a):
    _print(_run_op(a, "upscale", dict(src=_p(a.image), out=_p(a.out))))


def cmd_matte(a):
    _print(_run_op(a, "matte", dict(src=_p(a.image), out=_p(a.out))))


def cmd_recipe(a):
    if a.name in (None, "list"):
        return _print(recipes.list_recipes(Path.cwd()))
    inputs = {}
    for kv in a.inputs:
        k, _, v = kv.partition("=")
        try:
            v = json.loads(v)
        except ValueError:
            pass
        inputs[k] = v
    out_dir = _p(a.out_dir)
    client = None if a.local else service.running()
    if client:
        job = client.request("POST", "/jobs", {"kind": "recipe", "spec": {"recipe": a.name, "inputs": inputs,
                                                                          "out_dir": out_dir}})
        return _print(_follow(client, job))
    _print(recipes.run(a.name, inputs, out_dir, ops.Ctx(progress=lambda f, m: print(f"  [{f:4.0%}] {m}",
                                                                                  file=sys.stderr, flush=True))))


# ---------------------------------------------------------------- models

def cmd_models(a):
    if a.action == "list":
        total = 0
        for m in registry.models():
            here = registry.is_downloaded(m["id"])
            size = sum(f["bytes"] for f in m["files"])
            total += size if m.get("default", True) else 0
            flag = "" if m.get("default", True) else " (optional)"
            print(f"{'●' if here else '○'} {m['id']:22} {registry.gb(size):>8}  {m['group']:7} "
                  f"{m['licence'][:38]:38}  {m['summary'][:58]}{flag}")
        print(f"\n● downloaded  ○ not downloaded   ({registry.gb(total)} for the default set)")
    elif a.action == "find":
        q = " ".join(a.names).lower()
        for m in registry.models():
            if q in json.dumps([m["id"], m["name"], m["group"], m["capabilities"], m["summary"]]).lower():
                print(f"{m['id']:22} {m['summary']}")
    elif a.action == "show":
        _print(registry.model(a.names[0]))
    elif a.action in ("download", "restore"):
        try:
            registry.download(a.names or ["all"], force=a.force, accept_keys=a.accept)
        except registry.RegistryError as e:
            sys.exit(str(e))
    elif a.action == "verify":
        bad = 0
        for mid, state, detail in registry.verify(a.names, a.full):
            print(f"{state:15} {mid} {detail}")
            bad += state == "problem"
        sys.exit(1 if bad else 0)


# ---------------------------------------------------------------- check

def cmd_check(a):
    results = []

    def report(state, name, detail=""):
        results.append(state)
        print(f"{state:4}  {name}{'  ' + detail if detail else ''}", flush=True)

    from . import host
    from .engines import moss
    from .paths import KOKORO_PY, MOSS_PY, OPENMOSS_CLI, SD_CLI, TRELLIS_CLI
    hs = host.summary()
    gpu_ok = hs["gpu"] != "cpu"
    report("PASS" if gpu_ok else "WARN", "machine", f"{hs['os']} {hs['arch']}, GPU backend {hs['gpu']}, sandbox {hs['sandbox']}"
           + ("" if gpu_ok else ": no GPU found; images are slow and 3D takes hours on the CPU"))
    sound = ("MOSS env (MLX)", MOSS_PY, "moss") if moss.model_id() == "moss-sfx" else ("moss-tts-cli (openmoss)", OPENMOSS_CLI, "moss")
    for name, path, target in [("sd-cli", SD_CLI, "sd"), ("trellis-cli", TRELLIS_CLI, "trellis"), sound,
                               ("Kokoro env (optional)", KOKORO_PY, "speech")]:
        ok = Path(path).exists()
        report("PASS" if ok else "SKIP", name, portable(path) if ok else f"not built: make {target}")
    for name, path in [("Blender", blender()), ("ffmpeg", ffmpeg()), ("GIMP (optional)", gimp())]:
        report("PASS" if path else "INFO", name, path or "not installed")
    for mid, state, detail in registry.verify(full=a.full):
        report({"ok": "PASS", "not downloaded": "SKIP"}.get(state, "FAIL"), f"model {mid}", detail)
    if not a.quick:
        tmp = Path(a.keep).resolve() if a.keep else Path(tempfile.mkdtemp(prefix="aen-check-"))
        tmp.mkdir(parents=True, exist_ok=True)
        ctx = ops.Ctx(add_to_library=False)
        img = tmp / "image.png"
        jobs = [
            ("image", "image  z-image-turbo, 512 px, 4 steps", ["z-image-turbo"], lambda: ops.image(
                "a single wooden stool on a plain white background, studio photo", img, size=512, steps=4, seed=1,
                ctx=ctx)),
            ("klein", "image  flux2-klein-4b, 512 px, 4 steps", ["flux2-klein-4b"], lambda: ops.image(
                "a red apple on a wooden table", tmp / "klein.png", model="flux2-klein-4b", size=512, steps=4,
                seed=1, ctx=ctx)),
            ("sfx", "sfx    2 s, 10 steps, mastered", [moss.model_id()], lambda: ops.sfx(
                "a wooden door knocks twice", tmp / "sfx.wav", seconds=2, steps=10, seed=1, ctx=ctx)),
            ("3d", "3d     res 512 from the test image (about 5 minutes)", ["trellis2"], lambda: ops.model3d(
                img, tmp / "model.glb", res="512", seed=1, preview=False, ctx=ctx)),
        ]
        for key, label, needs, fn in jobs:
            if key in a.skip:
                continue
            missing = [m for m in needs if not registry.is_downloaded(m)]
            if key == "3d" and not img.exists():
                missing.append("the test image")
            if missing:
                report("SKIP", label, "needs " + ", ".join(missing))
                continue
            t = time.time()
            try:
                r = fn()
                report("PASS", label, f"{time.time() - t:.0f} s, checks {r.get('checks')}")
            except Exception as e:
                report("FAIL", label, str(e)[-500:])
        if a.keep:
            print(f"outputs kept in {portable(tmp)}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    n = {s: results.count(s) for s in ("PASS", "FAIL", "SKIP", "WARN")}
    print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped"
          + (f", {n['WARN']} warning(s)" if n["WARN"] else ""))
    sys.exit(1 if n["FAIL"] else 0)


# ---------------------------------------------------------------- library, policy, styles, service

def cmd_library(a):
    if a.action == "search":
        for r in library.search(" ".join(a.args) or None, a.kind, a.licence, a.project, a.origin, a.limit):
            print(f"{r['kind']:6} {r['origin']:10} {(r['licence'] or '?')[:22]:22} {portable(r['path'])}"
                  + (f"  ({r['similarity']:.2f})" if r.get("similarity") else ""))
    elif a.action == "import":
        if not a.source or not a.licence:
            sys.exit("import needs --source and --licence")
        n = library.import_dir(a.args[0], a.source, a.licence, a.url, a.author, a.tags or "", a.project)
        print(f"indexed {n} file(s) from {a.args[0]}")
    elif a.action == "show":
        _print(library.get(a.args[0]))
    elif a.action == "credits":
        text = library.credits(a.args[0] if a.args else Path.cwd())
        if a.write:
            Path(a.write).write_text(text)
            print(f"wrote {a.write}")
        else:
            print(text)
    elif a.action == "prune":
        print(f"removed {library.remove_missing()} entries whose files are gone")
    elif a.action == "reindex":
        print(f"re-embedded {library.reindex()} image(s) with the current scoring model")


def cmd_policy(a):
    d = Path(a.dir or Path.cwd())
    if a.action == "init":
        print(f"wrote {policy.init(policy.project_root(d))}")
    else:
        pol, root = policy.load(d)
        print(f"project: {root}")
        print(json.dumps(pol, indent=2) if pol else "no policy: everything allowed (aen policy init to add one)")


def cmd_style(a):
    if a.action == "list":
        for k, v in styles.list_styles(Path.cwd()).items():
            print(f"{k:16} {v}")
    else:
        _print(styles.summary(styles.find(a.name, near=Path.cwd())))


def cmd_service(a):
    if a.action == "start":
        c = service.ensure_running()
        print("running", c.request("GET", "/health"))
    elif a.action == "status":
        c = service.running()
        print(json.dumps(c.request("GET", "/health")) if c else "not running")
    elif a.action == "stop":
        c = service.running()
        if c:
            c.request("POST", "/shutdown", {})
            print("stopped")
        else:
            print("not running")
    elif a.action == "autostart":
        if a.state in ("on", "off"):
            print(service.autostart(a.state == "on"))
        else:
            print(service.autostart_status())
    elif a.action == "jobs":
        c = service.running()
        if not c:
            sys.exit("not running")
        for j in c.request("GET", "/jobs?limit=20"):
            print(f"{j['id']}  {j['status']:9} {j['progress']:4.0%}  {j['spec'].get('op') or j['spec'].get('recipe'):10}"
                  f"  {j['message']}")


def _src(a):
    return Path(a.source).read_text() if Path(a.source).is_file() else a.source


def cmd_diagram(a):
    _print(_run_op(a, "diagram", dict(source=_src(a), kind=a.kind, out=_p(a.out))))


def cmd_svg(a):
    _print(_run_op(a, "svg", dict(source=_src(a), out=_p(a.out), width=a.width)))


def cmd_music(a):
    extra = dict(seconds=a.seconds, seed=a.seed) if a.format == "sonic-pi" else {}
    _print(_run_op(a, "music", dict(source=_src(a), format=a.format, out=_p(a.out), master=not a.raw, **extra)))


def cmd_dialogue(a):
    _print(_run_op(a, "dialogue", dict(source=_src(a), kind=a.kind, out=_p(a.out))))



def cmd_where(a):
    """Where an app or program is installed on this machine (the editor extension asks this)."""
    from . import host
    if a.name == "machine":
        _print(host.summary())
        return
    found = host.find_app(a.name)
    if not found:
        sys.exit(f"{a.name} was not found")
    print(found)

def cmd_tools(a):
    from . import explicit
    if a.action == "list":
        for t in explicit.listing():
            print(f"{'✓' if t['installed'] else '✗'} {t['name']:15} {t['category']:8} {t['licence'][:26]:26}  {t['purpose']}")
    elif a.action == "check":
        from . import explicit_check
        results, d = explicit_check.check(a.names, a.keep)
        n = {s: sum(1 for v in results.values() if v[0] == s) for s in ("PASS", "FAIL", "SKIP")}
        print(f"\n{n['PASS']} passed, {n['FAIL']} failed, {n['SKIP']} skipped" + (f"; outputs in {d}" if a.keep else ""))
        sys.exit(1 if n["FAIL"] else 0)


def cmd_tool(a):
    from . import explicit
    sys.exit(explicit.run(a.name, a.extra, sandbox_dir=a.sandbox).returncode)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="aen", description="Aeneas Factory: local images, textures, 3D, sound.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("image", help="image from text (also image to image, tiles, references)")
    p.add_argument("prompt"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--model", choices=["z-image-turbo", "flux2-klein-4b"])
    p.add_argument("--size", type=int, default=1024); p.add_argument("-W", "--width", type=int)
    p.add_argument("-H", "--height", type=int); p.add_argument("--steps", type=int); p.add_argument("--cfg", type=float)
    p.add_argument("--neg"); p.add_argument("--init"); p.add_argument("--strength", type=float, default=0.6)
    p.add_argument("--ref", action="append", default=[]); p.add_argument("--tile", action="store_true")
    p.add_argument("--gpu-vae", action="store_true", help="GPU decode: known to give blank images with this build")
    _gen_args(p); p.set_defaults(func=cmd_image)

    p = sub.add_parser("edit", help="change a picture by instruction (FLUX.2 klein)")
    p.add_argument("instruction"); p.add_argument("src"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--ref", action="append", default=[]); _gen_args(p); p.set_defaults(func=cmd_edit)

    p = sub.add_parser("texture", help="seamless tile with PBR maps")
    p.add_argument("prompt"); p.add_argument("-o", "--out", required=True); p.add_argument("--size", type=int, default=512)
    p.add_argument("--no-pbr", action="store_true"); _gen_args(p); p.set_defaults(func=cmd_texture)

    p = sub.add_parser("3d", help="textured GLB from one image (TRELLIS.2)")
    p.add_argument("image"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--res", choices=["512", "1024", "1536"], default="512",
                   help="512 about 5 min (default), 1024 about 24 min, on an M5 Pro")
    p.add_argument("--no-texture", action="store_true"); p.add_argument("--bg-removal", choices=["threshold", "birefnet"])
    p.add_argument("--no-preview", action="store_true"); _gen_args(p, candidates=False); p.set_defaults(func=cmd_3d)

    p = sub.add_parser("cleanup", help="game-ready GLB: real size, origin, decimation, LODs (Blender)")
    p.add_argument("mesh"); p.add_argument("-o", "--out", required=True); p.add_argument("--size-m", type=float, default=1.0)
    p.add_argument("--faces", type=int, default=20000); p.add_argument("--lods", default="1,0.5,0.25")
    p.add_argument("--local", action="store_true"); p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("sfx", help="sound effect from a description (MOSS-SoundEffect)")
    p.add_argument("prompt"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--seconds", type=float, default=5.0); p.add_argument("--steps", type=int, default=100)
    p.add_argument("--cfg", type=float, default=4.0); p.add_argument("--raw", action="store_true",
                                                                     help="no trimming or loudness normalisation")
    _gen_args(p); p.set_defaults(func=cmd_sfx)

    p = sub.add_parser("speech", help="speech from text (Kokoro)")
    p.add_argument("text"); p.add_argument("-o", "--out", required=True); p.add_argument("--voice", default="af_heart")
    p.add_argument("--speed", type=float, default=1.0); p.add_argument("--local", action="store_true")
    p.set_defaults(func=cmd_speech)

    for name, fn, hlp in (("upscale", cmd_upscale, "4x larger (Real-ESRGAN)"),
                          ("matte", cmd_matte, "cut out the subject: transparent background (BiRefNet)")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("image"); p.add_argument("-o", "--out", required=True); p.add_argument("--local", action="store_true")
        p.set_defaults(func=fn)

    p = sub.add_parser("recipe", help="run a multi-step recipe: aen recipe prop --out-dir DIR subject='a bucket'")
    p.add_argument("name", nargs="?"); p.add_argument("inputs", nargs="*", help="key=value")
    p.add_argument("--out-dir", default="."); p.add_argument("--local", action="store_true")
    p.set_defaults(func=cmd_recipe)

    p = sub.add_parser("models", help="the model register: list, find, show, download, verify")
    p.add_argument("action", choices=["list", "find", "show", "download", "restore", "verify"])
    p.add_argument("names", nargs="*"); p.add_argument("--full", action="store_true")
    p.add_argument("--force", action="store_true"); p.add_argument("--accept", action="append", default=[],
                                                                   help="accept a licence, e.g. --accept dinov3")
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("diagram", help="diagram or chart from text: graphviz, d2, mermaid, vega-lite (PNG, or SVG by extension)")
    p.add_argument("source", help="the text, or a file holding it"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--kind", choices=["graphviz", "d2", "mermaid", "vega-lite"], default="graphviz")
    p.add_argument("--local", action="store_true"); p.set_defaults(func=cmd_diagram)

    p = sub.add_parser("svg", help="render an SVG (text or file) to PNG")
    p.add_argument("source"); p.add_argument("-o", "--out", required=True); p.add_argument("--width", type=int)
    p.add_argument("--local", action="store_true"); p.set_defaults(func=cmd_svg)

    p = sub.add_parser("music", help="music from ABC notation, a JSON note list, or Sonic Pi code; mastered")
    p.add_argument("source", help="ABC text or a .abc/.json/.rb file"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--format", choices=["abc", "notes", "sonic-pi"], default="abc")
    p.add_argument("--seconds", type=float, default=16, help="sonic-pi: how long to record (real time)")
    p.add_argument("--seed", type=int, help="sonic-pi: makes random choices repeatable")
    p.add_argument("--raw", action="store_true", help="no loudness normalisation")
    p.add_argument("--local", action="store_true"); p.set_defaults(func=cmd_music)

    p = sub.add_parser("dialogue", help="compile branching dialogue: ink (JSON) or yarn (.yarnc)")
    p.add_argument("source"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--kind", choices=["ink", "yarn"], default="ink")
    p.add_argument("--local", action="store_true"); p.set_defaults(func=cmd_dialogue)

    p = sub.add_parser("where", help="where an app is installed (blender, gimp, gimp-app, godot, ...), or `machine`")
    p.add_argument("name"); p.set_defaults(func=cmd_where)

    p = sub.add_parser("tools", help="explicit tools (code in, asset out): list, check [NAME...]")
    p.add_argument("action", choices=["list", "check"]); p.add_argument("names", nargs="*"); p.add_argument("--keep")
    p.set_defaults(func=cmd_tools)

    p = sub.add_parser("tool", help="run one explicit tool with the right environment: aen tool NAME [--sandbox DIR] -- args")
    p.add_argument("name"); p.add_argument("--sandbox", metavar="DIR",
                                           help="no network; writes only inside DIR (and temp folders)")
    p.set_defaults(func=cmd_tool)

    p = sub.add_parser("check", help="health check")
    p.add_argument("--quick", action="store_true"); p.add_argument("--full", action="store_true")
    p.add_argument("--skip", action="append", default=[], choices=["image", "klein", "sfx", "3d"])
    p.add_argument("--keep"); p.set_defaults(func=cmd_check)

    p = sub.add_parser("library", help="asset library: search, import, show, credits, prune, reindex")
    p.add_argument("action", choices=["search", "import", "show", "credits", "prune", "reindex"]); p.add_argument("args", nargs="*")
    for opt in ("--kind", "--licence", "--project", "--origin", "--source", "--url", "--author", "--tags", "--write"):
        p.add_argument(opt)
    p.add_argument("--limit", type=int, default=20); p.set_defaults(func=cmd_library)

    p = sub.add_parser("policy", help="a project's licence policy: init, show")
    p.add_argument("action", choices=["init", "show"]); p.add_argument("dir", nargs="?"); p.set_defaults(func=cmd_policy)

    p = sub.add_parser("style", help="style packs: list, show NAME")
    p.add_argument("action", choices=["list", "show"]); p.add_argument("name", nargs="?"); p.set_defaults(func=cmd_style)

    p = sub.add_parser("service", help="the factory service: start, status, stop, jobs, autostart on|off")
    p.add_argument("action", choices=["start", "status", "stop", "jobs", "autostart"])
    p.add_argument("state", nargs="?", choices=["on", "off"], help="with autostart: start at login or not")
    p.set_defaults(func=cmd_service)

    p = sub.add_parser("serve", help="run the factory service in the foreground")
    p.add_argument("--port", type=int)
    p.add_argument("--idle-exit", type=int, help="stop after this many idle minutes (default 30; 0 = never)")
    p.set_defaults(func=lambda a: service.serve(a.port, a.idle_exit))

    p = sub.add_parser("mcp", help="run the MCP server on stdio (for agents)")
    p.set_defaults(func=lambda a: __import__("aeneas.mcp_server", fromlist=["main"]).main())

    a = ap.parse_args(argv)
    a.extra = extra
    try:
        a.func(a)
    except (ops.OpError, registry.RegistryError, policy.PolicyError, styles.StyleError, recipes.RecipeError, service.ServiceError) as e:
        sys.exit(f"error: {e}")
    except Exception as e:
        from .checks import CheckFailed
        from .engines import EngineError
        if isinstance(e, (CheckFailed, EngineError)):
            sys.exit(f"error: {e}")
        raise
