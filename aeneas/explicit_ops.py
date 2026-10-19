"""Operations over explicit tools whose input is text, not code: diagrams, SVG, music, dialogue.
They run sandboxed (no network, writes only to the output folder), are checked like everything else,
and their provenance keeps the source text, so the asset can be edited and remade exactly."""
import json
import shutil
import tempfile
from pathlib import Path

from . import checks, explicit, ops, policy, provenance
from .engines import EngineError, post

DIAGRAMS = {"graphviz": ("dot", ".dot"), "d2": ("d2", ".d2"), "mermaid": ("mmdc", ".mmd"), "vega-lite": ("vl2png", ".json")}


def _record(out, tool, src_text, cmd, started, params, model_ids=(), found=None):
    rec = provenance.record(out, tool, list(model_ids), [], cmd, started, params=params, checks=found)
    rec["source"] = src_text  # the whole input: edit it and render again
    return rec


def _run(ctx, name, args, out, workdir):
    cmd = explicit.command(name, args, sandbox_dir=workdir)
    ctx.runner.run(cmd, Path(out).with_name(Path(out).name + ".log"), env=explicit.env(), cwd=workdir)
    return cmd


def diagram(source, out, kind="graphviz", ctx=None):
    """A diagram or chart from text: graphviz (DOT), d2, mermaid, or vega-lite (JSON spec). PNG, or SVG if out ends in .svg."""
    ctx = ctx or ops.Ctx()
    if kind not in DIAGRAMS:
        raise EngineError(f"kind must be one of {', '.join(DIAGRAMS)}")
    out = Path(out).expanduser().resolve()
    svg = out.suffix.lower() == ".svg"
    out = out if svg else out.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    started = provenance.datetime.datetime.now().astimezone()
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        tool, ext = DIAGRAMS[kind]
        src = Path(tmp) / f"diagram{ext}"
        src.write_text(source)
        target = Path(tmp) / ("out.svg" if svg else "out.png")
        if kind == "graphviz":
            args = [f"-T{'svg' if svg else 'png'}", "-Gdpi=144", "-o", str(target), str(src)]
        elif kind == "d2":
            args = [str(src), str(target)]
        elif kind == "mermaid":
            args = ["-i", str(src), "-o", str(target), "-b", "white", "-s", "2"]
        else:
            tool = "vl2svg" if svg else "vl2png"
            args = [str(src), str(target)] + ([] if svg else ["-s", "2"])
        ctx.progress(0.3, f"rendering {kind}")
        # Mermaid runs headless Chrome, whose own sandbox cannot nest inside sandbox-exec
        cmd = explicit.command(tool, args, sandbox_dir=None if kind == "mermaid" else tmp)
        ctx.runner.run(cmd, out.with_name(out.name + ".log"), env=explicit.env(), cwd=tmp)
        shutil.move(str(target), out)
    found = {"bytes": out.stat().st_size} if svg else checks.image(out, min_std=2)
    if svg and out.stat().st_size < 100:
        raise checks.CheckFailed(f"{out.name}: empty SVG")
    rec = _record(out, f"diagram ({kind})", source, cmd, started, {"kind": kind}, found=found)
    return ops._finish(ctx, out, rec, "image", tags=f"{kind} diagram")


def svg(source, out, width=None, ctx=None):
    """An SVG document rendered to PNG with resvg (optionally at a given width)."""
    ctx = ctx or ops.Ctx()
    out = ops._out(out, ".png")
    started = provenance.datetime.datetime.now().astimezone()
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        src = Path(tmp) / "in.svg"
        src.write_text(source)
        args = ([f"--width={int(width)}"] if width else []) + [str(src), str(Path(tmp) / "out.png")]
        cmd = _run(ctx, "resvg", args, out, tmp)
        shutil.move(str(Path(tmp) / "out.png"), out)
    found = checks.image(out, min_std=1)
    return ops._finish(ctx, out, _record(out, "svg (resvg)", source, cmd, started, {"width": width}, found=found),
                       "image", tags="svg")


def music(source, out, format="abc", master=True, ctx=None):
    """Music from notation, rendered with FluidSynth and the GeneralUser GS SoundFont.
    format "abc": ABC notation. format "notes": JSON {"tempo": 120, "tracks": [{"program": 0, "drums": false,
    "notes": [[pitch, start_beat, length_beats, velocity], ...]}]} (General MIDI programs; drums on channel 10)."""
    ctx = ctx or ops.Ctx()
    out = ops._out(out, ".wav")
    pol = policy.check_models(["generaluser-gs"], out)
    sf = explicit.soundfont()
    if not sf or not Path(sf).exists():
        raise EngineError("the SoundFont is missing: aen models download generaluser-gs")
    started = provenance.datetime.datetime.now().astimezone()
    midi = out.with_suffix(".mid")
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        t = Path(tmp)
        if format == "abc":
            (t / "in.abc").write_text(source)
            _run(ctx, "abc2midi", [str(t / "in.abc"), "-o", str(t / "in.mid")], out, tmp)
        elif format == "notes":
            spec = json.loads(source)
            (t / "spec.json").write_text(json.dumps(spec))
            (t / "make.py").write_text(MIDI_FROM_NOTES)
            _run(ctx, "python", [str(t / "make.py"), str(t / "spec.json"), str(t / "in.mid")], out, tmp)
        else:
            raise EngineError("format must be abc or notes")
        shutil.copy(t / "in.mid", midi)
        ctx.progress(0.5, "rendering with FluidSynth")
        raw = t / "raw.wav"
        cmd = _run(ctx, "fluidsynth", ["-ni", "-q", "-F", str(raw), "-r", "48000", "-g", "0.8", sf, str(t / "in.mid")], out, tmp)
        if master:
            ctx.runner.run(post.loudness_command(raw, out, trim=False), out.with_name(out.name + ".log"))
        else:
            shutil.move(str(raw), out)
    found = checks.audio(out)
    rec = _record(out, f"music ({format}, FluidSynth)", source, cmd, started,
                  {"format": format, "mastered": "loudness -18 LUFS, peak -1 dBTP" if master else None, "midi": midi.name},
                  model_ids=["generaluser-gs"], found=found) | {"policy": pol}
    res = ops._finish(ctx, out, rec, "audio", tags="music")
    res["midi"] = str(midi)
    res["waveform"] = str(post.waveform_png(out, out.with_name(out.stem + "_wave.png")))
    return res


MIDI_FROM_NOTES = r'''
import json, sys, pretty_midi
spec = json.load(open(sys.argv[1]))
tempo = float(spec.get("tempo", 120)); beat = 60.0 / tempo
pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
for tr in spec["tracks"]:
    inst = pretty_midi.Instrument(program=int(tr.get("program", 0)), is_drum=bool(tr.get("drums", False)), name=tr.get("name", ""))
    for n in tr["notes"]:
        pitch, start, length = int(n[0]), float(n[1]), float(n[2])
        vel = int(n[3]) if len(n) > 3 else 96
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=start * beat, end=(start + length) * beat))
    pm.instruments.append(inst)
pm.write(sys.argv[2])
'''


def dialogue(source, out, kind="ink", ctx=None):
    """Branching dialogue compiled for a game engine: ink (to JSON, for inkjs/ink-unity) or yarn (Yarn Spinner .yarnc)."""
    ctx = ctx or ops.Ctx()
    out = Path(out).expanduser().resolve()
    out = out.with_suffix(".json" if kind == "ink" else ".yarnc")
    out.parent.mkdir(parents=True, exist_ok=True)
    started = provenance.datetime.datetime.now().astimezone()
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        t = Path(tmp)
        if kind == "ink":
            (t / "story.ink").write_text(source)
            cmd = _run(ctx, "inkjs-compiler", [str(t / "story.ink"), "-o", str(t / "story.json")], out, tmp)
            made = t / "story.json"
        elif kind == "yarn":
            (t / "story.yarn").write_text(source)
            cmd = _run(ctx, "ysc", ["compile", str(t / "story.yarn"), "-o", str(t)], out, tmp)
            made = next(iter(t.glob("*.yarnc")), None)
        else:
            raise EngineError("kind must be ink or yarn")
        if not made or not made.exists() or made.stat().st_size < 20:
            raise checks.CheckFailed("the dialogue compiled to nothing")
        shutil.move(str(made), out)
    src_copy = out.with_suffix(".ink" if kind == "ink" else ".yarn")
    if not src_copy.exists() or src_copy.read_text() != source:  # never touch an unchanged source in an editor
        src_copy.write_text(source)
    rec = _record(out, f"dialogue ({kind})", source, cmd, started, {"kind": kind}, found={"bytes": out.stat().st_size})
    side = out.with_name(out.name + ".json")
    side.write_text(json.dumps(dict(rec, output_sha256=provenance.registry.sha256(out)), indent=2) + "\n")
    return {"path": str(out), "sidecar": str(side), "source": str(out.with_suffix(".ink" if kind == "ink" else ".yarn")),
            "kind": "dialogue"}


ops.OPS.update({"diagram": diagram, "svg": svg, "music": music, "dialogue": dialogue})
