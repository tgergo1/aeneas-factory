"""The factory service: one per machine. It owns the GPU through a single job queue, keeps the
sound model loaded between jobs, and serves a small JSON API on 127.0.0.1 to the MCP server and
the command line.

Security: it listens on 127.0.0.1 only; every request needs the token from ~/.aeneas/service.json
(readable by this user only); requests carrying a browser Origin header, or a Host other than
localhost, are refused. It runs only the factory's own operations and recipes, never code it is
sent, and it writes only to folders under the user's home (never into the factory itself)."""
import json
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, library, ops, recipes, registry, styles
from .engines import Cancelled, Runner
from .paths import FACTORY_PY, ROOT, STATE

INFO = STATE / "service.json"
JOBS = STATE / "jobs"
DEFAULT_PORT = 7861
IDLE_EXIT_MINUTES = 30  # a service started on demand stops after this long without work; 0 = never
AGENT_LABEL = "com.aeneas-factory.service"
AGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"
PATH_ARGS = {"src", "init", "image"}
LIST_PATH_ARGS = {"refs"}
# Operations that render text with explicit tools: no models, about a second each. They run in their own lane
# so a diagram or a tune is not stuck behind a 3D job on the GPU lane.
LIGHT_OPS = {"diagram", "svg", "music", "dialogue"}


class Job:
    def __init__(self, kind, spec):
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.spec = kind, spec
        self.status, self.progress, self.message = "queued", 0.0, "waiting in the queue"
        self.created, self.started, self.finished = time.time(), None, None
        self.result, self.error = None, None
        self.runner = Runner()
        self.done = threading.Event()

    def public(self):
        return {"id": self.id, "kind": self.kind, "spec": self.spec, "status": self.status,
                "progress": round(self.progress, 3), "message": self.message, "created": self.created,
                "started": self.started, "finished": self.finished, "result": self.result, "error": self.error}

    def save(self):
        JOBS.mkdir(parents=True, exist_ok=True)
        (JOBS / f"{self.id}.json").write_text(json.dumps(self.public(), indent=2, default=str))


class Factory:
    def __init__(self):
        self.jobs, self.order = {}, []
        self.lanes = {"gpu": queue.Queue(), "light": queue.Queue()}
        self.last_activity = time.time()
        self.idle_exit_minutes = 0
        for q in self.lanes.values():
            threading.Thread(target=self._work, args=(q,), daemon=True).start()

    def touch(self):
        self.last_activity = time.time()

    def busy(self):
        return any(j.status in ("queued", "running") for j in self.jobs.values())

    def idle_seconds(self):
        return 0.0 if self.busy() else time.time() - self.last_activity

    def submit(self, kind, spec):
        check_spec(kind, spec)
        job = Job(kind, spec)
        self.touch()
        self.jobs[job.id] = job
        self.order.append(job.id)
        job.save()
        light = kind == "op" and spec.get("op") in LIGHT_OPS
        self.lanes["light" if light else "gpu"].put(job)
        return job

    def _work(self, q):
        while True:
            job = q.get()
            if job.status == "cancelled":
                continue
            job.status, job.started, job.message = "running", time.time(), "starting"
            job.save()

            def progress(f, msg, job=job):
                job.progress, job.message = max(job.progress, min(f, 1.0)), msg

            # "library": false (live previews) keeps a result out of the asset library
            ctx = ops.Ctx(runner=job.runner, progress=progress, add_to_library=job.spec.get("library", True) is not False)
            try:
                if job.kind == "op":
                    job.result = ops.run(job.spec["op"], dict(job.spec.get("args", {})), ctx)
                else:
                    job.result = recipes.run(job.spec["recipe"], job.spec.get("inputs", {}), job.spec["out_dir"], ctx)
                job.status, job.progress, job.message = "done", 1.0, "done"
            except Cancelled:
                job.status, job.message = "cancelled", "cancelled"
            except Exception as e:
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"
                job.message = "failed"
                (JOBS / f"{job.id}.trace").write_text(traceback.format_exc())
            job.finished = time.time()
            job.save()
            job.done.set()
            self.touch()

    def cancel(self, job_id):
        job = self.jobs[job_id]
        if job.status == "queued":
            job.status, job.message = "cancelled", "cancelled before it started"
            job.done.set()
            job.save()
        elif job.status == "running":
            job.runner.cancel()
        return job


def _under_home(p):
    p = Path(p).expanduser().resolve()
    home = Path.home().resolve()
    return (p == home or home in p.parents) and ROOT not in (p, *p.parents)


def check_spec(kind, spec):
    """Only the factory's own operations, on files under the user's home, outside the factory."""
    if kind == "op":
        from . import extra  # noqa: F401
        if spec.get("op") not in ops.OPS:
            raise ValueError(f"unknown operation {spec.get('op')}")
        args = spec.get("args", {})
        if "out" not in args or not _under_home(args["out"]):
            raise ValueError("out must be a path under your home folder, outside the factory")
        for k in PATH_ARGS & set(args):
            if not (_under_home(args[k]) and Path(args[k]).expanduser().is_file()):
                raise ValueError(f"{k} must be an existing file under your home folder")
        for k in LIST_PATH_ARGS & set(args):
            for v in args[k]:
                if not (_under_home(v) and Path(v).expanduser().is_file()):
                    raise ValueError(f"{k}: {v} must be an existing file under your home folder")
    elif kind == "recipe":
        if not _under_home(spec.get("out_dir", "/")):
            raise ValueError("out_dir must be under your home folder, outside the factory")
        recipes.validate(recipes.find(spec["recipe"], near=spec["out_dir"]))
    else:
        raise ValueError("kind must be op or recipe")


def make_handler(factory, token, port):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _guard(self):
            if self.headers.get("Origin") or self.headers.get("Host") not in allowed_hosts:
                self._send(403, {"error": "refused: browser or foreign host"})
                return False
            if not secrets.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"):
                self._send(401, {"error": "missing or wrong token"})
                return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            parts = [p for p in u.path.split("/") if p]
            if parts != ["health"]:
                factory.touch()
            try:
                if parts == ["health"]:
                    from . import scoring
                    return self._send(200, {"ok": True, "version": __version__, "pid": os.getpid(),
                                            "queued": sum(j.status == "queued" for j in factory.jobs.values()),
                                            "running": sum(j.status == "running" for j in factory.jobs.values()),
                                            "idle_seconds": round(factory.idle_seconds()),
                                            "idle_exit_minutes": factory.idle_exit_minutes,
                                            "models_loaded": scoring.loaded() + (["moss-sfx"] if _moss_loaded() else [])})
                if parts == ["jobs"]:
                    ids = factory.order[-int(q.get("limit", 20)):]
                    return self._send(200, [factory.jobs[i].public() for i in reversed(ids)])
                if len(parts) == 2 and parts[0] == "jobs":
                    job = factory.jobs.get(parts[1])
                    if not job:
                        return self._send(404, {"error": "no such job"})
                    job.done.wait(min(float(q.get("wait", 0)), 120))
                    return self._send(200, job.public())
                if parts == ["models"]:
                    return self._send(200, [{**{k: m[k] for k in ("id", "name", "group", "summary", "licence")},
                                             "downloaded": registry.is_downloaded(m["id"])} for m in registry.models()])
                if parts == ["capabilities"]:
                    from . import extra  # noqa: F401
                    near = q.get("project")
                    return self._send(200, {"operations": sorted(ops.OPS), "recipes": recipes.list_recipes(near),
                                            "styles": styles.list_styles(near)})
                if parts == ["library"]:
                    return self._send(200, library.search(q.get("q"), q.get("kind"), q.get("licence"),
                                                          q.get("project"), q.get("origin"), int(q.get("limit", 20))))
                return self._send(404, {"error": "unknown path"})
            except Exception as e:
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})

        def do_POST(self):
            if not self._guard():
                return
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
                if parts == ["jobs"]:
                    job = factory.submit(body["kind"], body["spec"])
                    return self._send(200, job.public())
                if len(parts) == 3 and parts[0] == "jobs" and parts[2] == "cancel":
                    return self._send(200, factory.cancel(parts[1]).public())
                if parts == ["shutdown"]:
                    self._send(200, {"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return None
                return self._send(404, {"error": "unknown path"})
            except Exception as e:
                return self._send(400, {"error": f"{type(e).__name__}: {e}"})

    return H


def _moss_loaded():
    from .engines import moss
    return bool(moss._worker and moss._worker.proc and moss._worker.proc.poll() is None)


def serve(port=None, idle_exit=None):
    """Run the service. idle_exit: minutes without work before it stops by itself (0 = never)."""
    if running():
        print("the factory service is already running", flush=True)
        return
    port = int(port or os.environ.get("AEN_PORT", DEFAULT_PORT))
    idle_exit = IDLE_EXIT_MINUTES if idle_exit is None else int(idle_exit)
    STATE.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    factory = Factory()
    factory.idle_exit_minutes = idle_exit
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(factory, token, port))
    if idle_exit > 0:
        def watch():
            while True:
                time.sleep(30)
                if factory.idle_seconds() > idle_exit * 60:
                    print(f"idle for {idle_exit} minutes: stopping (the next request starts it again)", flush=True)
                    server.shutdown()
                    return
        threading.Thread(target=watch, daemon=True).start()
    fd = os.open(INFO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"port": port, "token": token, "pid": os.getpid(), "version": __version__, "root": str(ROOT)}, f)
    print(f"aeneas-factory service on 127.0.0.1:{port} (pid {os.getpid()}, "
          f"{'stops after ' + str(idle_exit) + ' idle minutes' if idle_exit else 'stays running'})", flush=True)
    try:
        server.serve_forever()
    finally:
        INFO.unlink(missing_ok=True)
        if _moss_loaded():
            from .engines import moss
            moss._worker.stop()


# ---------------------------------------------------------------- client

class ServiceError(RuntimeError):
    """The service refused or failed a request; the message is meant for the user."""


class Client:
    def __init__(self, info):
        self.base = f"http://127.0.0.1:{info['port']}"
        self.token = info["token"]

    def request(self, method, path, body=None, timeout=150):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.token}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise ServiceError(json.loads(e.read() or b"{}").get("error", str(e)))


def running():
    try:
        info = json.loads(INFO.read_text())
        c = Client(info)
        c.request("GET", "/health", timeout=3)
        return c
    except Exception:
        return None


def ensure_running(wait=30):
    c = running()
    if c:
        return c
    STATE.mkdir(parents=True, exist_ok=True)
    py = FACTORY_PY if FACTORY_PY.exists() else Path(sys.executable)
    with open(STATE / "service.log", "a") as log:
        subprocess.Popen([str(py), "-m", "aeneas", "serve"], cwd=str(ROOT), stdout=log, stderr=log,
                         start_new_session=True)
    t = time.time()
    while time.time() - t < wait:
        time.sleep(0.5)
        c = running()
        if c:
            return c
    raise RuntimeError(f"the factory service did not start; see {STATE / 'service.log'}")


# ---------------------------------------------------------------- start at login (macOS LaunchAgent)

def autostart_plist():
    import plistlib
    return plistlib.dumps({
        "Label": AGENT_LABEL,
        "ProgramArguments": [str(ROOT / "bin" / "aen"), "serve", "--idle-exit", "0"],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},  # restart after a crash, not after a clean stop
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "StandardOutPath": str(STATE / "service.log"),
        "StandardErrorPath": str(STATE / "service.log"),
    })


def autostart(on):
    uid = os.getuid()
    if on:
        STATE.mkdir(parents=True, exist_ok=True)
        AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["launchctl", "bootout", f"gui/{uid}/{AGENT_LABEL}"], capture_output=True)
        c = running()
        if c:  # a service started on demand: replace it with the login one
            c.request("POST", "/shutdown", {})
            time.sleep(1)
        AGENT_PLIST.write_bytes(autostart_plist())
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT_PLIST)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"launchctl bootstrap failed: {r.stderr.strip()}")
        return f"on: starts at login and stays running ({AGENT_PLIST})"
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{AGENT_LABEL}"], capture_output=True)
    AGENT_PLIST.unlink(missing_ok=True)
    return "off: the service starts on demand and stops after 30 idle minutes"


def autostart_status():
    if not AGENT_PLIST.exists():
        return "off (starts on demand, stops after 30 idle minutes)"
    r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{AGENT_LABEL}"], capture_output=True, text=True)
    return "on (starts at login)" + ("" if r.returncode == 0 else ", but not loaded right now")
