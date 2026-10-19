import json

import pytest

from aeneas import explicit, explicit_check, ops


def test_every_explicit_tool_has_a_real_check():
    assert set(explicit.TOOLS) == set(explicit_check.TESTS)


def test_sandbox_blocks_network_and_stray_writes(tmp_path):
    prof = explicit.sandbox_profile(tmp_path)
    assert "(deny network*)" in prof and "(deny file-write*)" in prof
    assert str(tmp_path.resolve()) in prof


def test_text_operations_are_registered():
    from aeneas import extra  # noqa: F401
    assert {"diagram", "svg", "music", "dialogue"} <= set(ops.OPS)


needs = lambda *names: pytest.mark.skipif(not all(explicit.locate(n) for n in names), reason="explicit tools not installed")


@needs("dot")
def test_diagram_renders_and_keeps_its_source(tmp_path):
    from aeneas import extra  # noqa: F401
    r = ops.run("diagram", {"source": "digraph { a -> b }", "out": tmp_path / "d.png"}, ops.Ctx(add_to_library=False))
    rec = json.loads(open(r["sidecar"]).read())
    assert rec["source"] == "digraph { a -> b }" and r["checks"]["width"] > 10


@needs("abc2midi", "fluidsynth")
def test_music_from_abc_is_real_audio(tmp_path):
    from aeneas import extra  # noqa: F401
    if not explicit.soundfont():
        pytest.skip("SoundFont not downloaded")
    r = ops.run("music", {"source": "X:1\nL:1/4\nK:C\nCEGc|\n", "out": tmp_path / "m.wav", "master": False},
                ops.Ctx(add_to_library=False))
    assert r["checks"]["seconds"] > 1 and r["checks"]["rms_dbfs"] > -50


def test_tools_are_found_with_launchds_minimal_path():
    import subprocess
    import sys
    code = "from aeneas import explicit, paths; print(bool(paths.ffmpeg()), explicit.locate('dot') is not None)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(explicit.ROOT),
                         env={"PATH": "/usr/bin:/bin", "HOME": __import__("os").environ["HOME"], "PYTHONPATH": str(explicit.ROOT)})
    if explicit.locate("dot") is None:
        pytest.skip("graphviz not installed")
    assert out.stdout.split() == ["True", "True"], out.stderr


def test_sandboxed_commands_do_not_name_the_user_in_records():
    from aeneas import provenance
    from aeneas.paths import HOME
    cmd = ["sandbox-exec", "-p", explicit.sandbox_profile(HOME + "/somewhere/out"), "dot", HOME + "/x.dot"]
    recorded = [provenance._arg(c) for c in cmd]
    assert not any(HOME in c for c in recorded), recorded
    assert "~/somewhere/out" in recorded[2] and recorded[-1].endswith("x.dot")
