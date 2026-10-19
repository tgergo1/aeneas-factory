# Aeneas Factory: notes for AI agents

For Claude Code, Codex or any agent asked to make images, textures, 3D models, sound effects or other content on a machine with this factory installed.

## Prefer the MCP tools

If the `aeneas` MCP server is connected, use its tools; they queue on the shared factory service, check every result and return a thumbnail.

1. Call `capabilities` once (with `project_dir`) to see the recipes, styles and downloaded models.
2. Before generating, `search_assets` may already have what is needed (generated earlier, or a downloaded CC0 pack).
3. For a finished asset, prefer `run_recipe`: `prop` (game-ready 3D model with LODs), `texture` (seamless PBR set), `sfx` (mastered sound effect), `sprite` (cut-out 2D art).
4. For single steps: `generate_image`, `edit_image`, `make_texture`, `image_to_3d`, `generate_sound`, `generate_speech`, `upscale_image`, `remove_background`.
5. **Look at the thumbnail of every result** before using it. If it is wrong, try another seed or `candidates` 3-4; do not keep a result you have not looked at.
6. Long jobs return a `job_id`; call `job_status` to wait. 3D takes about 5 minutes at res 512.
7. Always pass the project's absolute `project_dir`; results go to `<project_dir>/generated/`.
8. If a tool says the project's licence policy refuses a model, tell the owner; do not work around it.

## Or the command line

| Need | Command |
|---|---|
| Image from text | `bin/aen image "<prompt>" -o out.png` (`--model flux2-klein-4b`, `--candidates 3`, `--style NAME`) |
| Edit an image | `bin/aen edit "<what to change>" in.png -o out.png` |
| Seamless texture with PBR maps | `bin/aen texture "<surface>" -o tile.png` |
| 3D model from one image | `bin/aen 3d object.png -o object.glb` (res 512 by default, about 5 minutes) |
| Game-ready model | `bin/aen recipe prop --out-dir DIR subject="<object>" size_m=0.5` |
| Sound effect | `bin/aen sfx "<description>" --seconds 5 -o out.wav` |
| Speech | `bin/aen speech "<text>" -o out.wav --voice bm_george` |
| Upscale · cut out | `bin/aen upscale in.png -o out.png` · `bin/aen matte in.png -o out.png` |
| Find existing assets | `bin/aen library search "<words>" --licence CC0-1.0` |

- `bin/aen models list` shows what is downloaded; `bin/aen check --quick` diagnoses problems.
- Every output gets `<output>.json` beside it and the same record inside it: models, licences, prompt, seed, versions, checks. Keep it with the file.
- Pass `--seed` when a result must be reproducible.
- For 3D, describe one object on a plain white background, generate the image, then make the model from it (or just use the `prop` recipe).
- Never download a second copy of a model that `models.json` lists. A model several projects could use belongs in this factory's register.
- `bin/aen library credits <project>` writes the credits page from everything generated and imported.

## Explicit tools: code and text in, assets out

When the result must be exact, editable or consistent (icons, UI, diagrams, pixel art, music, CAD parts, levels, dialogue), write a source and render it instead of generating. `aen tools list` shows what is installed; `aen tools check` proves each works.

Over MCP (text in, sandboxed, checked, source kept in the provenance):
- `render_diagram` (graphviz, d2, mermaid, vega-lite), `render_svg` (any SVG you write), `compose_music` (ABC notation, or a JSON note list, played with General MIDI instruments and mastered), `compile_dialogue` (Ink or Yarn Spinner), `explicit_tools` (the full list).

From a shell, `aen tool NAME [--sandbox OUTDIR] -- args` runs any of them with the right environment. Use `--sandbox OUTDIR` for anything that runs code (Python, Csound, SuperCollider, OpenSCAD): no network, writes only inside OUTDIR.

| Need | How |
|---|---|
| Pixel art from a picture | `aen tool magick -- in.png -filter point -resize 64x64 -dither FloydSteinberg -remap palette.png sprite.png`, then `-scale 800%` to preview; or Pillow in `aen tool python` (`Image.quantize(palette=...)`) |
| Sprite sheets, outlines, shadows | `aen tool magick -- montage ...`, `-morphology`, `-shadow` |
| Icons, logos, UI art | write SVG, `render_svg`; trace a picture to SVG with `vtracer` in `aen tool python` |
| Diagrams and charts | `render_diagram` |
| Procedural textures | GLSL through `moderngl` (offscreen) or `opensimplex` noise in `aen tool python`; tile-check with `aen texture`'s seam check |
| Music | `compose_music` (ABC or notes); `music21` / `pretty_midi` scripts for more; `lilypond` for sheet music; instruments: General MIDI programs |
| Sound design | `csound` (.csd), `sclang` (SuperCollider, `Score.recordNRT`), `faust` + `faust2sndfile`; effects with `sox` or `pedalboard` |
| Solid / CAD parts | `openscad -o part.stl part.scad`, or `build123d` in `aen tool python`; convert with `trimesh` |
| Mesh processing | UVs: `xatlas`; retopology: Blender `quadriflow_remesh`; repair and simplify: `pymeshlab`; validate: `aen tool gltf-validator -- m.glb`; compress: `aen tool gltfpack -- -i in.glb -o out.glb -cc`; GPU textures: `basisu -ktx2` |
| Rigging and motion capture | Blender: Rigify, BVH import and retargeting (`aen tool blender -- -b --python script.py`) |
| Physics | `pymunk` (2D), `mujoco` (3D) in `aen tool python` |
| Animation and titles | `manim` (use `Text`, not LaTeX) |
| Levels and maps | Tiled (`aen tool tiled -- --export-map json in.tmx out.json`, `tmxrasterizer` for a picture), `godot --headless` |
| 3D from your own photos | `colmap` (no GPU here; slow but works) |

Keep each source next to its output and in the project; the source is the asset's real definition.

## Prefer the right tool over a workaround

An editor or an existing free asset often beats drawing something in code or generating it from nothing. Combine them: a generated concept image as a modelling reference in Blender, a Poly Haven texture cleaned up in GIMP, a generated sound trimmed with ffmpeg.

| Tool | Use it for |
|---|---|
| Blender (`/Applications/Blender.app/Contents/MacOS/Blender -b --python script.py`) | Modelling, retopology, UVs, baking, rigging, animation, rendering, converting glTF, FBX, OBJ, USD. `scripts/render_glb.py` renders a `.glb` preview |
| GIMP (`/Applications/GIMP.app/Contents/MacOS/gimp-console` for batch work) | Retouching, masks, tiling, sprite sheets, icons |
| ffmpeg | Cutting, encoding and converting video and audio |

## Free sources to look in first

Check each asset's own licence on its page; several sites mix licences.

| Source | What | Usual licence |
|---|---|---|
| [Inside Out Library](https://insideoutlibrary.com/) | Over 1.8 million historical illustrations, diagrams and ornaments from old books | The site says free to use for anything; still record the source book |
| [Poly Haven](https://polyhaven.com/) | HDRIs, PBR textures, 3D models | CC0 |
| [ambientCG](https://ambientcg.com/) | PBR textures and materials | CC0 |
| [Kenney](https://kenney.nl/) | Game kits (3D, 2D, UI), sound packs | CC0 |
| [OpenGameArt](https://opengameart.org/) | Sprites, models, music, sound | Mixed: CC0, CC BY, CC BY-SA, GPL |
| [Wikimedia Commons](https://commons.wikimedia.org/) | Photos, scans, illustrations, audio | Per file |
| [Sketchfab](https://sketchfab.com/) | 3D models (filter to downloadable) | Per model, often CC BY 4.0 |
| [Fab](https://www.fab.com/) | Epic's store, including Quixel Megascans | Per listing |
| [Mixamo](https://www.mixamo.com/) | Rigged characters and motion capture | Adobe terms: royalty-free |
| [MakeHuman](https://www.makehumancommunity.org/) | Human base meshes, clothing, hair | Mostly CC0 |
| [Pexels](https://www.pexels.com/) | Stock photos and video | Pexels licence |
| [Google Fonts](https://fonts.google.com/) | Fonts | OFL or Apache-2.0 |
| [LibriVox](https://librivox.org/) | Public-domain audiobook recordings | Public domain |
| [CMU Motion Capture](http://mocap.cs.cmu.edu/) | Motion capture clips (BVH) | Free for any use |
| [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) | Robot models | Per model, often BSD-3-Clause or Apache-2.0 |

## Rules

- **Record every asset.** Import downloaded packs into the library with their licence (`aen library import DIR --source ... --licence ...`); generated files are recorded automatically. `aen library credits` then writes the credits page.
- **Check commercial use** before anything ships or is shown publicly. Prefer CC0 and other permissive licences; treat CC BY-SA, GPL and non-commercial as the owner's decision. TRELLIS.2's `dinov3.gguf` is under Meta's DINOv3 License: read it before shipping 3D models.
- **Credit what requires credit** (CC BY and similar) wherever the work is shown.
- **Ask the owner before** buying anything, creating an account or signing in to a store.
- **Project rules win.** A project's own instructions may forbid sources or require stricter licences.
