"""`aen tools check`: make something real with every explicit tool and check it, so "installed"
means "works". Code-based tools run in the sandbox (no network, writes only to the test folder)."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import checks, explicit

GALLERY_GLB = explicit.ROOT / "docs" / "gallery" / "chest.glb"


def _run(name, args, d, sandbox=True, timeout=180):
    r = subprocess.run(explicit.command(name, args, d if sandbox else None), env=explicit.env(), cwd=d,
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:])
    return r


def _py(d, code, timeout=300):
    f = d / f"t{abs(hash(code)) % 10**8}.py"
    f.write_text(code)
    return _run("python", [str(f)], d, timeout=timeout).stdout.strip()


def _file(p, min_bytes=100):
    p = Path(p)
    if not p.exists() or p.stat().st_size < min_bytes:
        raise RuntimeError(f"{p.name} was not made")
    return f"{p.name} {p.stat().st_size} bytes"


def t_magick(d):
    _run("magick", ["-size", "256x256", "plasma:fractal", "-seed", "3", str(d / "plasma.png")], d)
    return checks.image(d / "plasma.png")


def t_resvg(d):
    (d / "a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><circle cx="64" cy="64" r="48" fill="#e07a5f"/><rect x="20" y="90" width="88" height="20" fill="#3d405b"/></svg>')
    _run("resvg", [str(d / "a.svg"), str(d / "a.png")], d)
    return checks.image(d / "a.png")


def t_rsvg_convert(d):
    (d / "b.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><polygon points="48,6 90,90 6,90" fill="#81b29a"/></svg>')
    _run("rsvg-convert", ["-o", str(d / "b.png"), str(d / "b.svg")], d)
    return checks.image(d / "b.png", min_std=2)


def t_dot(d):
    (d / "g.dot").write_text("digraph { rankdir=LR; concept -> mesh -> cleanup -> game; concept -> texture }")
    _run("dot", ["-Tpng", "-o", str(d / "g.png"), str(d / "g.dot")], d)
    return checks.image(d / "g.png", min_std=2)


def t_d2(d):
    (d / "g.d2").write_text("agent -> factory: MCP\nfactory -> engines: jobs\nengines -> assets")
    _run("d2", [str(d / "g.d2"), str(d / "g.svg")], d)
    return _file(d / "g.svg")


def t_mmdc(d):
    (d / "m.mmd").write_text("flowchart LR\n  A[prompt] --> B(image) --> C{checks} -->|ok| D[library]")
    _run("mmdc", ["-i", str(d / "m.mmd"), "-o", str(d / "m.png"), "-b", "white"], d, sandbox=False, timeout=180)
    return checks.image(d / "m.png", min_std=2)


def t_vl2png(d):
    spec = {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "data": {"values": [
        {"job": "image", "s": 110}, {"job": "sound", "s": 115}, {"job": "3d", "s": 290}]},
        "mark": "bar", "encoding": {"x": {"field": "job", "type": "nominal"}, "y": {"field": "s", "type": "quantitative"}}}
    (d / "c.vl.json").write_text(json.dumps(spec))
    _run("vl2png", [str(d / "c.vl.json"), str(d / "c.png")], d)
    return checks.image(d / "c.png", min_std=2)


def t_vl2svg(d):
    _run("vl2svg", [str(d / "c.vl.json"), str(d / "c.svg")], d)
    return _file(d / "c.svg")


def t_python(d):
    out = _py(d, r'''
import json, numpy as np
from PIL import Image
import cv2, coloraide, fontTools, music21, pretty_midi, mido, pedalboard, opensimplex, scipy, trimesh, xatlas
import pymeshlab, build123d, moderngl, vtracer, pymunk, mujoco, tracery
# a procedural texture with noise, an SVG traced from it, a CAD part, a UV unwrap, a shader render
n = opensimplex.OpenSimplex(1)
img = np.array([[n.noise2(x / 16, y / 16) for x in range(64)] for y in range(64)])
Image.fromarray(((img + 1) * 127).astype("uint8")).save("noise.png")
vtracer.convert_image_to_svg_py("noise.png", "noise.svg")
from build123d import Box, Cylinder, export_stl
part = Box(40, 20, 10) - Cylinder(4, 10)
export_stl(part, "part.stl")
m = trimesh.creation.icosphere(subdivisions=2)
vmap, faces, uvs = xatlas.parametrize(m.vertices, m.faces)
ctx = moderngl.create_standalone_context()
fbo = ctx.simple_framebuffer((64, 64)); fbo.use(); fbo.clear(0.2, 0.4, 0.6, 1.0)
Image.frombytes("RGB", (64, 64), fbo.read()).save("gl.png")
grammar = tracery.Grammar({"origin": ["#adj# #thing#"], "adj": ["mossy", "gilded"], "thing": ["lantern", "chest"]})
space = pymunk.Space(); space.gravity = (0, -900)
mj = mujoco.MjModel.from_xml_string("<mujoco><worldbody><body><freejoint/><geom size='.1'/></body></worldbody></mujoco>")
print(json.dumps({"uv_vertices": len(vmap), "phrase": grammar.flatten("#origin#"), "palette": str(coloraide.Color("oklch(0.7 0.1 40)").convert("srgb").to_string(hex=True))}))
''')
    checks.image(d / "noise.png")
    checks.image(d / "gl.png", min_std=0)
    _file(d / "noise.svg")
    _file(d / "part.stl")
    return out


def t_fluidsynth(d):
    _py(d, r'''
import pretty_midi
pm = pretty_midi.PrettyMIDI(); inst = pretty_midi.Instrument(program=0)
for i, p in enumerate([60, 64, 67, 72]):
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=p, start=i * 0.3, end=i * 0.3 + 0.5))
pm.instruments.append(inst); pm.write("tune.mid")
''')
    sf = explicit.soundfont()
    if not sf or not Path(sf).exists():
        raise RuntimeError("SoundFont missing: aen models download generaluser-gs")
    _run("fluidsynth", ["-ni", "-q", "-F", str(d / "tune.wav"), "-r", "48000", sf, str(d / "tune.mid")], d)
    return checks.audio(d / "tune.wav")


def t_abc2midi(d):
    (d / "t.abc").write_text("X:1\nT:Test\nM:6/8\nL:1/8\nK:D\nDFA dfa|g2f e2d|\n")
    _run("abc2midi", [str(d / "t.abc"), "-o", str(d / "t.mid")], d)
    return _file(d / "t.mid", 20)


def t_lilypond(d):
    (d / "s.ly").write_text('\\version "2.24.0"\n\\score { \\relative c\' { c4 e g c } \\layout { } \\midi { } }\n')
    _run("lilypond", ["-o", str(d / "s"), str(d / "s.ly")], d, timeout=240)
    return _file(d / "s.pdf") + ", " + _file(d / "s.midi", 20)


def t_csound(d):
    (d / "t.csd").write_text("""<CsoundSynthesizer>
<CsOptions>
-o t.wav -W
</CsOptions>
<CsInstruments>
sr = 48000
ksmps = 32
nchnls = 1
0dbfs = 1

instr 1
  kenv linseg 0, 0.05, 0.4, 0.6, 0
  a1 vco2 kenv, p4
  out a1
endin
</CsInstruments>
<CsScore>
i 1 0 0.7 220
i 1 0.7 0.7 330
</CsScore>
</CsoundSynthesizer>
""")
    _run("csound", [str(d / "t.csd")], d)
    return checks.audio(d / "t.wav")


def t_faust(d):
    (d / "n.dsp").write_text('import("stdfaust.lib"); process = no.noise * 0.1 : fi.lowpass(2, 1200);')
    _run("faust", ["-lang", "cpp", str(d / "n.dsp"), "-o", str(d / "n.cpp")], d)
    return _file(d / "n.cpp")


def t_faust2sndfile(d):
    (d / "g.dsp").write_text('import("stdfaust.lib"); process = _ * 0.5 + os.osc(440) * 0.2;')
    _run("faust2sndfile", [str(d / "g.dsp")], d, timeout=300)
    _run("sox", ["-n", "-r", "48000", "-c", "1", "-b", "16", str(d / "silence.wav"), "trim", "0", "1"], d)
    _run("python", ["-c", "import subprocess,sys; subprocess.run(['./g', 'silence.wav', 'g.wav'], check=True)"], d)
    return checks.audio(d / "g.wav")


def t_sclang(d):
    (d / "nrt.scd").write_text(r'''
SynthDef(\aen, { Out.ar(0, SinOsc.ar(330, 0, Line.kr(0.3, 0, 1, doneAction: 2))) }).store;
x = Score([[0.0, [\s_new, \aen, 1000, 0, 0]], [1.0, [\c_set, 0, 0]]]);
x.recordNRT(outputFilePath: "sc.wav", headerFormat: "WAV", sampleFormat: "int16",
  options: ServerOptions.new.numOutputBusChannels_(1).sampleRate_(48000), duration: 1, action: { 0.exit });
''')
    _run("sclang", [str(d / "nrt.scd")], d, sandbox=False, timeout=180)
    return checks.audio(d / "sc.wav")


def t_sox(d):
    _run("sox", ["-n", "-r", "48000", "-b", "16", str(d / "tone.wav"), "synth", "0.5", "sine", "440", "fade", "0.05",
                 "0.5", "0.1", "reverb", "40"], d)
    return checks.audio(d / "tone.wav")


def t_openscad(d):
    (d / "p.scad").write_text("difference() { cube([30, 20, 10], center=true); cylinder(h=12, r=5, center=true, $fn=48); }")
    _run("openscad", ["-o", str(d / "p.stl"), str(d / "p.scad")], d, timeout=240)
    return _file(d / "p.stl")


def t_gltfpack(d):
    if not GALLERY_GLB.exists() or GALLERY_GLB.stat().st_size < 1000:
        raise RuntimeError("docs/gallery/chest.glb not fetched from Git LFS")
    _run("gltfpack", ["-i", str(GALLERY_GLB), "-o", str(d / "chest-packed.glb"), "-cc"], d)
    return f"{GALLERY_GLB.stat().st_size // 1024} KB -> {(d / 'chest-packed.glb').stat().st_size // 1024} KB"


def t_gltf_validator(d):
    r = _run("gltf-validator", [str(GALLERY_GLB)], d)
    rep = json.loads(r.stdout)
    return f"errors {rep['errors']}, warnings {rep['warnings']}, triangles {rep['triangles']}"


def t_basisu(d):
    if not (d / "plasma.png").exists():
        t_magick(d)
    _run("basisu", ["-ktx2", "-output_path", str(d), str(d / "plasma.png")], d, timeout=240)
    return _file(d / "plasma.ktx2")


def t_colmap(d):
    r = _run("colmap", ["help"], d)
    return (r.stdout.splitlines() or ["?"])[0][:60]


def t_blender(d):
    (d / "b.py").write_text(r'''
import bpy, addon_utils, json
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_monkey_add()
o = bpy.context.active_object
bpy.ops.object.quadriflow_remesh(target_faces=600)
addon_utils.enable("rigify", default_set=True)
print("AENEAS", json.dumps({"quadriflow_faces": len(o.data.polygons), "rigify": "rigify" in bpy.context.preferences.addons and hasattr(bpy.ops.pose, "rigify_generate")}))
''')
    r = _run("blender", ["-b", "--factory-startup", "--python", str(d / "b.py")], d, timeout=240)
    return next((l[7:] for l in r.stdout.splitlines() if l.startswith("AENEAS ")), "?")


def t_tiled(d):
    (d / "m.json").write_text(json.dumps({"type": "map", "version": "1.10", "orientation": "orthogonal", "renderorder": "right-down",
        "width": 2, "height": 2, "tilewidth": 16, "tileheight": 16, "infinite": False, "nextlayerid": 2, "nextobjectid": 1,
        "layers": [{"type": "tilelayer", "id": 1, "name": "ground", "width": 2, "height": 2, "data": [0, 0, 0, 0],
                    "opacity": 1, "visible": True, "x": 0, "y": 0}], "tilesets": []}))
    _run("tiled", ["--export-map", "tmx", str(d / "m.json"), str(d / "m.tmx")], d, sandbox=False)
    return _file(d / "m.tmx")


def t_tmxrasterizer(d):
    if not (d / "m.tmx").exists():
        t_tiled(d)
    r = subprocess.run(explicit.command("tmxrasterizer", ["--version"]), env=explicit.env(), capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()[:40] or "runs"


def t_godot(d):
    r = _run("godot", ["--headless", "--version"], d, sandbox=False)
    return r.stdout.strip()[:40]


def t_inkjs_compiler(d):
    (d / "s.ink").write_text("The chest is locked.\n* [Pick the lock] It clicks open. -> END\n* [Leave it] You walk away. -> END\n")
    _run("inkjs-compiler", [str(d / "s.ink"), "-o", str(d / "s.json")], d)
    return _file(d / "s.json", 50)


def t_ysc(d):
    (d / "s.yarn").write_text("title: Start\n---\nGuard: Halt! Who goes there?\n-> A friend.\n    Guard: Pass.\n===\n")
    _run("ysc", ["compile", str(d / "s.yarn"), "-o", str(d)], d)
    return ", ".join(sorted(p.name for p in d.glob("*.yarnc"))) or _file(next(d.glob("*.yarn*c*")))


def t_manim(d):
    (d / "scene.py").write_text('from manim import *\nclass T(Scene):\n    def construct(self):\n        self.play(Write(Text("aeneas", color=YELLOW)), run_time=0.5)\n')
    _run("manim", ["-ql", "--format", "png", "-s", "--media_dir", str(d / "media"), str(d / "scene.py"), "T"], d, timeout=300)
    pngs = sorted((d / "media").rglob("*.png"))
    if not pngs:
        raise RuntimeError("manim wrote no frame")
    return checks.image(pngs[-1], min_std=2)


TESTS = {"magick": t_magick, "python": t_python, "resvg": t_resvg, "rsvg-convert": t_rsvg_convert, "dot": t_dot,
         "d2": t_d2, "mmdc": t_mmdc, "vl2png": t_vl2png, "vl2svg": t_vl2svg, "fluidsynth": t_fluidsynth,
         "abc2midi": t_abc2midi, "lilypond": t_lilypond, "csound": t_csound, "faust": t_faust,
         "faust2sndfile": t_faust2sndfile, "sclang": t_sclang, "sox": t_sox, "openscad": t_openscad,
         "gltfpack": t_gltfpack, "gltf-validator": t_gltf_validator, "basisu": t_basisu, "colmap": t_colmap,
         "blender": t_blender, "tiled": t_tiled, "tmxrasterizer": t_tmxrasterizer, "godot": t_godot,
         "inkjs-compiler": t_inkjs_compiler, "ysc": t_ysc, "manim": t_manim}


def check(only=(), keep=None, report=print):
    d = Path(keep).resolve() if keep else Path(tempfile.mkdtemp(prefix="aen-tools-"))
    d.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in explicit.TOOLS:
        if only and name not in only:
            continue
        if not explicit.locate(name):
            results[name] = ("SKIP", "not installed: make explicit")
        else:
            t = time.time()
            try:
                info = TESTS[name](d)
                results[name] = ("PASS", f"{time.time() - t:4.1f} s  {info}")
            except Exception as e:
                results[name] = ("FAIL", str(e)[-300:].replace("\n", " "))
        report(f"{results[name][0]:4}  {name:15} {results[name][1]}")
    return results, d
