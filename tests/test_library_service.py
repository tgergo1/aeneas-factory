import json
import secrets
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from aeneas import library, ops, service


def test_library_import_search_credits(tmp_path, noise_png):
    pack = tmp_path / "proj" / "assets" / "kenney"
    pack.mkdir(parents=True)
    (pack / "wooden_crate.png").write_bytes(noise_png.read_bytes())
    (pack / "readme.txt").write_text("not an asset")
    n = library.import_dir(pack, "Kenney", "CC0", url="https://kenney.nl", project=tmp_path / "proj")
    assert n == 1
    hits = library.search("crate")
    assert hits and hits[0]["licence"] == "CC0-1.0" and hits[0]["origin"] == "downloaded"
    assert library.search("crate", licence="CC-BY-4.0") == []
    text = library.credits(tmp_path / "proj")
    assert "Kenney" in text and "CC0-1.0" in text


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    done = []

    def fake(out, text="hi", ctx=None):
        (tmp_path / "o.txt").write_text(text)
        ctx.progress(0.5, "half")
        done.append(out)
        return {"path": str(out)}

    ops.OPS["fake"] = fake
    token = secrets.token_urlsafe(8)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), service.make_handler(service.Factory(), token, 0))
    port = srv.server_address[1]
    srv.RequestHandlerClass = service.make_handler(service.Factory(), token, port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield port, token, tmp_path, done
    srv.shutdown()
    ops.OPS.pop("fake", None)


def call(port, token, method, path, body=None, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def test_service_runs_a_job(server):
    port, token, home, done = server
    job = call(port, token, "POST", "/jobs", {"kind": "op", "spec": {"op": "fake", "args": {"out": str(home / "a.png")}}})
    job = call(port, token, "GET", f"/jobs/{job['id']}?wait=5")
    assert job["status"] == "done" and job["result"]["path"].endswith("a.png")


def test_service_refuses_without_token(server):
    port, *_ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        call(port, "wrong", "GET", "/health")
    assert e.value.code == 401


def test_service_refuses_browsers(server):
    port, token, *_ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        call(port, token, "GET", "/health", headers={"Origin": "https://evil.example"})
    assert e.value.code == 403


def test_service_refuses_paths_outside_home(server):
    port, token, home, _ = server
    with pytest.raises(urllib.error.HTTPError):
        call(port, token, "POST", "/jobs", {"kind": "op", "spec": {"op": "fake", "args": {"out": "/etc/x.png"}}})
    with pytest.raises(urllib.error.HTTPError):
        call(port, token, "POST", "/jobs", {"kind": "op", "spec": {"op": "nope", "args": {"out": str(home / "x")}}})


def test_service_refuses_writing_into_the_factory(server):
    port, token, *_ = server
    from aeneas.paths import ROOT
    with pytest.raises(ValueError):
        service.check_spec("op", {"op": "fake", "args": {"out": str(ROOT / "bin" / "x.png")}})


def test_dinov3_attribution_in_records_and_credits(tmp_path, noise_png):
    from aeneas import provenance
    entry = provenance.model_entry("trellis2")
    assert entry["attribution_required"] == "Built with DINOv3"
    assert "attribution_required" not in provenance.model_entry("z-image-turbo")
    proj = tmp_path / "game"
    (proj / ".git").mkdir(parents=True)
    f = proj / "model_preview.png"
    f.write_bytes(noise_png.read_bytes())
    library.add_generated(f, {"models": [entry], "prompt": "a crate"})
    assert "Built with DINOv3" in library.credits(proj)


def test_search_ignores_filler_words(tmp_path, noise_png):
    f = tmp_path / "p" / "x.png"
    f.parent.mkdir()
    f.write_bytes(noise_png.read_bytes())
    library.add_generated(f, {"models": [], "prompt": "a brass lantern on a table"})
    assert not [r for r in library.search("a car on a road") if r["path"] == str(f.resolve()) and not r.get("similarity")]
    assert [r for r in library.search("brass lantern") if r["path"] == str(f.resolve())]


def test_idle_time_counts_only_without_work():
    import time
    f = service.Factory()
    f.last_activity = time.time() - 100
    assert f.idle_seconds() >= 99
    job = service.Job("op", {})
    job.status = "running"
    f.jobs[job.id] = job
    assert f.idle_seconds() == 0  # never idle while a job runs


def test_scoring_check_does_not_load_torch():
    import subprocess
    import sys
    code = "import sys; from aeneas import scoring; scoring.available('image'); print('torch' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(service.ROOT),
                         env={**__import__("os").environ, "PYTHONPATH": str(service.ROOT)}).stdout.strip()
    assert out == "False"  # the service stays small; torch lives only in the scoring worker


def test_login_agent_runs_the_service_without_idle_exit():
    import plistlib
    d = plistlib.loads(service.autostart_plist())
    assert d["Label"] == service.AGENT_LABEL and d["RunAtLoad"] is True
    assert d["ProgramArguments"][-3:] == ["serve", "--idle-exit", "0"]
    assert d["KeepAlive"] == {"SuccessfulExit": False}
