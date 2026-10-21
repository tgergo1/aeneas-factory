# Aeneas Factory

**Local generation of images, textures, 3D models, sound effects and speech on macOS, Linux or Windows, plus 30 explicit tools that turn code and text into exact assets (music, live-coded Sonic Pi tracks, diagrams, icons, pixel art, CAD parts, levels, dialogue), built so that AI agents can use it safely and every result can be trusted.** Open models, pinned and checksummed. One shared service with a job queue. An MCP server for Claude Code and Codex. Automatic checks so a blank image is never reported as a success. Provenance written into every file. A licence policy per project. Recipes that turn a request into a finished asset. A searchable library of everything made or downloaded.

**Built with DINOv3**: the 3D generator (TRELLIS.2) uses Meta's DINOv3 image features under the [DINOv3 License](https://ai.meta.com/resources/models-and-libraries/dinov3-license); see [Licences](#licences).

<p align="center">
  <img src="docs/factory.svg" alt="Diagram: agents use the MCP server, scripts the aen command line, people the VS Code extension, ComfyUI and Blender. All work goes through one factory service: licence policy, engine, checks, ranked candidates, provenance, asset library. Engines: stable-diffusion.cpp (Z-Image Turbo, FLUX.2 klein), trellis.cpp (TRELLIS.2), MOSS-SoundEffect and Kokoro (MLX on Apple Silicon, openmoss and PyTorch elsewhere), Real-ESRGAN, BiRefNet, ComfyUI, Blender, ffmpeg. Explicit tools: diagrams, SVG, music, dialogue and 25 more, sandboxed." width="100%">
</p>

## What it does

| | |
|---|---|
| **Generate** | Images from text (Z-Image Turbo, FLUX.2 [klein] 4B), image editing from references, seamless textures with PBR maps, textured 3D models from one image (TRELLIS.2), sound effects (MOSS-SoundEffect), speech (Kokoro), 4x upscaling (Real-ESRGAN), background removal (BiRefNet) |
| **Compose** | 30 explicit tools, no model weights: diagrams and charts (Graphviz, D2, Mermaid, Vega-Lite), SVG icons and UI art, pixel art (ImageMagick), music from ABC notation or note lists played with General MIDI instruments, live-coded music in Sonic Pi (rendered silently to WAV), synthesis (Csound, SuperCollider, Faust), CAD parts (OpenSCAD, build123d), mesh work (xatlas, PyMeshLab, gltfpack), levels (Tiled, Godot) and branching dialogue (Ink, Yarn Spinner). Code that runs is sandboxed: no network, writes only to its output folder |
| **Check** | Every output is checked before it counts: blank or flat images, visible seams in tiles, silent audio, empty or flat meshes. A failure is an error, never a result |
| **Choose** | `--candidates N` makes several, drops the failures, ranks the rest by how well they match the prompt (SigLIP for images, CLAP for sound) and keeps the best, recording all of them |
| **Record** | Provenance inside the file (PNG text, glTF `extras`, WAV `INFO`) and beside it (`<file>.json`): the models with every file's SHA-256, the factory and tool versions, prompt, seed, settings, checks and the licence policy that applied. For explicit tools the record keeps the whole source text, so the asset can be edited and made again exactly |
| **Govern** | A per-project licence policy (`.aeneas/policy.toml`) decides which models and downloaded assets may be used. Models whose licence asks for agreement (DINOv3) download only after you accept it |
| **Assemble** | Recipes run several steps in a row: `prop` (concept → 3D → Blender clean-up to real size with LODs), `texture` (tile → PBR set), `sfx` (takes → trimmed, -18 LUFS), `sprite` (art → cut-out) |
| **Remember** | An asset library indexes everything generated and every downloaded pack you import, searchable by words and, for images, by meaning; `aen library credits` writes a project's credits page |
| **Stay consistent** | Style packs (prompt, negative, reference images, LoRAs, palette) keep a project's look the same across every asset |
| **Serve** | One factory service per machine owns the GPU with a single queue, keeps the sound model loaded, and serves the MCP server and the command line on 127.0.0.1 with a token |

## Gallery

Made by this repository ([`scripts/make_gallery.sh`](scripts/make_gallery.sh), fixed seeds); each file has its provenance beside it in [`docs/gallery`](docs/gallery).

| | |
|---|---|
| <img src="docs/gallery/chest.png" width="100%" alt="A weathered wooden treasure chest"> | <img src="docs/gallery/chest-blue.png" width="100%" alt="The same chest painted blue"> |
| **Text to image**, Z-Image Turbo<br>`aen image "a weathered wooden treasure chest …" -o chest.png` | **Editing**, FLUX.2 [klein] 4B<br>`aen edit "paint the wooden planks a deep blue, …" chest.png -o chest-blue.png` |
| <img src="docs/gallery/chest-3d.png" width="100%" alt="A Blender render of the 3D model made from the chest picture"> | <img src="docs/gallery/cobbles-2x2.png" width="100%" alt="A cobblestone texture repeated two by two without seams"> |
| **Image to 3D**, TRELLIS.2: [`chest.glb`](docs/gallery/chest.glb), rendered in Blender<br>`aen 3d chest.png -o chest.glb` | **Seamless texture** with PBR maps, shown 2x2<br>`aen texture "rounded grey river cobblestones …" -o cobbles.png` |

<img src="docs/gallery/chest-creak-wave.png" width="100%" alt="Waveform of the generated chest sound">

**Sound effect**, MOSS-SoundEffect: [`chest-creak.wav`](docs/gallery/chest-creak.wav) · `aen sfx "an old wooden chest lid creaks open slowly, then thuds shut" -o chest-creak.wav`

### Explicit tools: written, not generated

No models: each one is rendered from a short source kept beside it in [`docs/gallery/explicit`](docs/gallery/explicit), and its record holds that source.

| | | |
|---|---|---|
| <img src="docs/gallery/explicit/chest-pixel.png" width="100%" alt="The treasure chest as 48-pixel pixel art"> | <img src="docs/gallery/explicit/potion.png" width="100%" alt="A purple potion flask icon drawn as SVG"> | <img src="docs/gallery/explicit/pipeline.png" width="100%" alt="A diagram of the prop pipeline drawn with D2"> |
| **Pixel art**, ImageMagick: the chest above cut out, cut to 48 px and 12 colours, enlarged without smoothing<br>`aen tool magick -- chest.png … -colors 12 -scale 800% chest-pixel.png` | **Icon** from SVG, resvg: [`potion.svg`](docs/gallery/explicit/potion.svg)<br>`aen svg potion.svg --width 256 -o potion.png` | **Diagram**, D2: [`pipeline.d2`](docs/gallery/explicit/pipeline.d2)<br>`aen diagram pipeline.d2 --kind d2 -o pipeline.png` |

<img src="docs/gallery/explicit/tavern_wave.png" width="100%" alt="Waveform of the tavern tune">

**Music** from ABC notation, a jig on a flute, FluidSynth with GeneralUser GS, mastered to -18 LUFS: [`tavern.abc`](docs/gallery/explicit/tavern.abc) → [`tavern.wav`](docs/gallery/explicit/tavern.wav) and [`tavern.mid`](docs/gallery/explicit/tavern.mid) · `aen music tavern.abc -o tavern.wav`

<img src="docs/gallery/explicit/groove_wave.png" width="100%" alt="Waveform of the Sonic Pi groove">

**Live-coded music**, Sonic Pi: four `live_loop`s (drums, hats, a TB-303 bass line, Prophet chords through reverb), recorded for 12 s with seed 3, nothing played aloud: [`groove.rb`](docs/gallery/explicit/groove.rb) → [`groove.wav`](docs/gallery/explicit/groove.wav) · `aen music groove.rb --format sonic-pi --seconds 12 --seed 3 -o groove.wav`

### Recipes: finished assets, not raw generations

These came out of one command each, through the factory service, with every intermediate step and its provenance kept ([`docs/gallery/recipes`](docs/gallery/recipes)).

| | | |
|---|---|---|
| <img src="docs/gallery/recipes/bucket-render.png" width="100%" alt="A game-ready wooden bucket model"> | <img src="docs/gallery/recipes/oak-2x2.png" width="100%" alt="An oak plank texture tiled 2x2"> | <img src="docs/gallery/recipes/key.png" width="100%" alt="A golden key on a transparent background"> |
| **`prop`**: best of 2 concept images → TRELLIS.2 → Blender: 0.4 m tall, origin at the bottom, 149,556 faces cut to LODs of 20,000 / 10,000 / 5,000 ([`bucket.glb`](docs/gallery/recipes/bucket.glb), [manifest](docs/gallery/recipes/bucket-manifest.json)). 11.6 minutes | **`texture`**: best of 2 tiles by prompt match, seam checked (edge jump 0.53x the texture's own detail), plus height, [normal](docs/gallery/recipes/oak-normal.png), roughness and AO maps | **`sprite`**: best of 2 images, cut out onto transparency with BiRefNet |

<img src="docs/gallery/recipes/door-wave.png" width="100%" alt="Waveform of the generated door sound">

**`sfx`**: two takes ranked by CLAP, silence trimmed, loudness normalised to -18 LUFS with a -1 dBTP peak: [`door.wav`](docs/gallery/recipes/door.wav)

## Quick start

The installer is [`install.py`](install.py) (Python 3.10 or later, nothing else); on macOS and Linux `make <step>` runs the same steps. It detects the GPU and builds the engines for it: Metal on Apple Silicon, CUDA when the CUDA toolkit is installed, Vulkan when the Vulkan SDK (`glslc`) is, else the CPU (`AEN_GPU=cuda|vulkan|cpu` chooses).

| | Prerequisites |
|---|---|
| macOS | `xcode-select --install`, then `brew install cmake uv git-lfs ffmpeg` |
| Linux (Debian, Ubuntu) | `sudo apt install build-essential cmake ninja-build git git-lfs curl ffmpeg bubblewrap`, and `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/)); a GPU toolkit (CUDA, or `glslc libvulkan-dev` for Vulkan) for fast images and 3D |
| Windows | `winget install Git.Git Kitware.CMake Ninja-build.Ninja astral-sh.uv Gyan.FFmpeg Python.Python.3.12` and Visual Studio Build Tools with C++ (`Microsoft.VisualStudio.2022.BuildTools`); run the installer from a *Developer PowerShell for VS* |

```bash
git clone https://github.com/tgergo1/aeneas-factory.git
cd aeneas-factory
make install GROUPS=image                 # images only: tools + 15.7 GB of models + a quick check
                                          # Windows: py install.py install --groups image
```

Everything (all four core models, about 40 GB; read the [DINOv3 licence](https://ai.meta.com/resources/models-and-libraries/dinov3-license) first, since TRELLIS.2 needs it):

```bash
make install ACCEPT=dinov3                # py install.py install --accept dinov3
make extras models-extras                 # optional: ranking, background removal, speech, upscaling, music (2.1 GB)
make explicit                             # optional: the 30 explicit tools (system packages, Python, Node, .NET; no models)
```

The explicit tools need none of the models; `make factory explicit` and `aen models download generaluser-gs` (32 MB, for music) are enough for them alone. `python install.py help` lists every step.

Then (on Windows the commands are `bin\aen.cmd`, `bin\ai-image.cmd`, ...):

```bash
export PATH="$PWD/bin:$PATH"
aen image "a lighthouse on a cliff at dawn, watercolour" -o lighthouse.png --candidates 3
aen texture "weathered oak planks" -o oak.png
aen recipe prop --out-dir props subject="a wooden water bucket with iron hoops" size_m=0.4
aen sfx "rain on a tin roof, distant thunder" --seconds 10 -o rain.wav
aen speech "Welcome to the village." -o welcome.wav --voice bm_george
aen music docs/gallery/explicit/tavern.abc -o tavern.wav
aen diagram 'digraph { idea -> sketch -> asset }' -o flow.png
aen tools check                           # prove every explicit tool works
```

## Platforms

| | macOS, Apple Silicon | Linux x64 | Windows x64 |
|---|---|---|---|
| Images, upscaling (stable-diffusion.cpp) | Metal | CUDA, Vulkan or CPU | CUDA, Vulkan or CPU |
| 3D (trellis.cpp) | Metal | CUDA or Vulkan (CPU works but takes hours) | CUDA or Vulkan |
| Sound effects (MOSS-SoundEffect) | MLX | openmoss (C++/GGML: CUDA, Vulkan, ROCm or CPU) | openmoss |
| Speech (Kokoro) | MLX | PyTorch (CPU is enough) | PyTorch |
| Sandbox for the explicit tools | `sandbox-exec` | bubblewrap (`bwrap`) | none: notation renders run unsandboxed, code (Sonic Pi) is refused unless `AEN_ALLOW_UNSANDBOXED=1` |
| Start at login | LaunchAgent | systemd user unit | per-user Run entry |
| Explicit tools from | Homebrew ([`Brewfile`](Brewfile)) | apt, dnf, pacman or Homebrew ([`deps/`](deps)) | winget ([`deps/winget.txt`](deps/winget.txt)); 8 are not on winget |
| Tested | yes: everything, every release (M5 Pro) | tests, docs, commands and the editor extension on a self-hosted runner; the engines are built there on request | not yet |

The same models, recipes, records and MCP tools on all three; a record says which engine and platform made a file. Intel Macs use the Linux and Windows variants of sound and speech.

## Using it from an AI agent

Register the MCP server once; it starts the factory service by itself when needed:

```bash
claude mcp add --scope user aeneas -- "$PWD/bin/aen" mcp
codex mcp add aeneas -- "$PWD/bin/aen" mcp
```

On Windows use `bin\aen.cmd` in place of `bin/aen`; `python install.py mcp-info` prints the exact lines for this machine.

21 tools:

- **Generate**: `generate_image`, `edit_image`, `make_texture`, `image_to_3d`, `generate_sound`, `generate_speech`, `upscale_image`, `remove_background`, `run_recipe`
- **Compose** from text the agent writes: `render_diagram` (Graphviz, D2, Mermaid, Vega-Lite), `render_svg`, `compose_music` (ABC notation or a JSON note list with General MIDI instruments, or Sonic Pi code), `compile_dialogue` (Ink or Yarn Spinner), `explicit_tools` (what else is installed and how to call it)
- **Jobs and records**: `capabilities`, `job_status`, `cancel_job`, `list_jobs`, `search_assets`, `get_provenance`, `project_credits`

- Every finished result comes back with a **thumbnail the agent can look at**: the image, a 2x2 tile preview, a render of the 3D model, a rendered diagram or icon, or a waveform. Candidates come back as a contact sheet.
- Long work (3D takes minutes) returns a **job id at once**; `job_status` waits for it.
- Outputs go to `<project_dir>/generated/`. The server **never runs code it is sent, never downloads models, and writes only under your home folder, outside the factory**. The compose tools take notation and markup (DOT, SVG, ABC, Ink), not programs, and run sandboxed.
- [`AGENTS.md`](AGENTS.md) tells agents how to use all this, plus Blender, GIMP and free asset libraries, with the licence rules. `scripts/mcp_smoke.py` tests the whole path the way an agent uses it.

## In the editor

The VS Code extension ([`editors/vscode`](editors/vscode); also Cursor, Windsurf and VSCodium) puts the factory in the editor: diagrams, SVG, ABC music and Ink or Yarn dialogue render beside their source on every save; `.glb` models open in a 3D viewer with their real size and `.wav` files with their waveform and levels; a Provenance view shows how the open file was made (models, licences, required credits, prompt, seed, checks, and whether the file still matches its record); and there are a Library search with thumbnails, a Jobs view, generation commands, and hand-off to Blender, GIMP and Godot. It is a client of the same service, so the editor, the command line and agents share one queue and one library.

```bash
make vscode-install       # build the extension and install it (needs Node; VSCODE_CLI=cursor for Cursor; Windows: py install.py vscode-install)
```

## The command line

`aen <command> --help` for every option. `ai-image`, `ai-3d`, `ai-sfx`, `ai-music`, `ai-diagram`, … are short for `aen image`, `aen 3d`, `aen sfx`, `aen music`, `aen diagram`, … When the factory service is running, commands queue there (nothing fights over the GPU); `--local` runs them in the calling process.

| Command | Does |
|---|---|
| `aen image PROMPT -o out.png` | Text to image. `--model flux2-klein-4b`, `--size`, `--seed`, `--candidates N`, `--style NAME`, `--init photo.png --strength 0.4`, `--ref img.png`, `--tile` |
| `aen edit INSTRUCTION src.png -o out.png` | Change a picture by instruction (FLUX.2 klein) |
| `aen texture PROMPT -o tile.png` | Seamless tile (seam checked) with height, normal, roughness and AO maps and a 2x2 preview |
| `aen 3d image.png -o model.glb` | Textured GLB (TRELLIS.2). `--res 512` (default, about 5 min) or `1024` (about 24 min); renders a preview |
| `aen cleanup model.glb -o game.glb` | Blender: real size (`--size-m`), origin at the bottom centre, decimated (`--faces`), LODs (`--lods 1,0.5,0.25`) |
| `aen sfx PROMPT -o out.wav` | Sound effect, trimmed and loudness-normalised (`--raw` to skip); `--seconds`, `--candidates` |
| `aen speech TEXT -o out.wav` | Speech (Kokoro): `--voice af_heart, af_bella, am_michael, am_adam, bf_emma, bm_george`, `--speed` |
| `aen upscale in.png -o out.png` · `aen matte in.png -o out.png` | 4x upscale · transparent cut-out |
| `aen recipe NAME --out-dir DIR key=value …` | Run a recipe; `aen recipe list` shows them with their inputs |
| `aen models list / find / show / download / verify` | The model register; `download` takes `all`, a group or ids, and `--accept KEY` |
| `aen library search / import / show / credits / prune` | The asset library |
| `aen policy init / show` · `aen style list / show` | Licence policy · style packs |
| `aen service start / status / stop / jobs / autostart on\|off` · `aen mcp` | The factory service (and starting it at login) · the MCP server on stdio |
| `aen check` | Health check: tools, every model file, and a real job through each generator |
| `aen diagram SOURCE -o out.png` | Diagram or chart from text or a file: `--kind graphviz` (default), `d2`, `mermaid`, `vega-lite`; SVG output if `-o` ends in `.svg` |
| `aen svg SOURCE -o out.png` | Render SVG to PNG (`--width`) |
| `aen music SOURCE -o out.wav` | Music from ABC notation, `--format notes` for a JSON note list (both also write the `.mid`), or `--format sonic-pi --seconds 16 [--seed N]` for Sonic Pi code; mastered unless `--raw` |
| `aen dialogue SOURCE -o story.json` | Compile Ink to JSON (inkjs, ink-unity), or `--kind yarn` for Yarn Spinner |
| `aen tools list / check` · `aen tool NAME [--sandbox DIR] -- args` | The explicit tools: list, prove each works, run any one with the right environment |

## Explicit tools: code and text in, assets out

Generation is the wrong tool when the result must be exact, editable or the same every time: an icon in a UI, a chart, a tune that loops, a part with real dimensions, a level, a dialogue tree. For those the factory installs 30 tools that turn code or text into assets, with no model weights: `make explicit` (system packages: Homebrew from the [`Brewfile`](Brewfile) on macOS, apt, dnf, pacman or Homebrew from [`deps/`](deps) on Linux, winget on Windows; then a locked Python environment, locked Node packages, Yarn Spinner, and the GeneralUser GS SoundFont). On Linux, packages that need `sudo` are printed for you to run, or installed with `python install.py explicit --system`. Tools that are not installed are simply unavailable; `aen tools list` shows which. `aen tools check` makes something real with each one and checks it.

| Area | Tools |
|---|---|
| Images and vector | ImageMagick, resvg, rsvg-convert, OpenCV, vtracer (raster to SVG), coloraide (palettes, contrast), fontTools (fonts) |
| Diagrams and charts | Graphviz, D2, Mermaid, Vega-Lite |
| Music | ABC notation (abc2midi), music21, pretty_midi, mido, LilyPond, FluidSynth with GeneralUser GS, Sonic Pi |
| Sound design | Csound, SuperCollider, Faust, sox, pedalboard |
| Procedural | moderngl (GLSL shaders offscreen), opensimplex noise, Taichi simulations |
| 3D | OpenSCAD, build123d, trimesh, xatlas, pymeshlab, gltfpack, glTF-Validator, Basis Universal, COLMAP, Blender (QuadriFlow, Rigify) |
| Physics and motion | pymunk, MuJoCo, Manim |
| Levels and dialogue | Tiled and tmxrasterizer, Godot (headless), Ink (inkjs), Yarn Spinner |

Four of them have their own commands and MCP tools that take text (`aen diagram`, `aen svg`, `aen music`, `aen dialogue`; `render_diagram`, `render_svg`, `compose_music`, `compile_dialogue`): sandboxed, checked like every other output, and recorded with their source. Every tool runs as `aen tool NAME -- args` with the environment it needs (tool paths, .NET, the SoundFont):

```bash
aen tools list                                           # what is installed, by area, with licences
aen tool magick -- in.png -filter point -resize 64x64 -dither None -colors 16 sprite.png
aen tool openscad --sandbox out -- -o out/gear.stl gear.scad
aen tool python --sandbox out -- make_level.py           # trimesh, build123d, pymunk, music21, … are importable
aen tool gltfpack -- -i model.glb -o model-small.glb -cc
aen tool blender -- -b --python rig.py                   # Rigify, BVH retargeting, QuadriFlow
```

`--sandbox DIR` runs the tool sandboxed: no network, and writes only inside `DIR` (and the temporary and cache folders), with `sandbox-exec` on macOS and bubblewrap on Linux. Use it for anything that executes code. Windows has no comparable sandbox, so there `--sandbox` and Sonic Pi code are refused unless you set `AEN_ALLOW_UNSANDBOXED=1`. [`AGENTS.md`](AGENTS.md) has a table of which tool to reach for, need by need.

FontForge was left out because Homebrew disabled it (it fails macOS Gatekeeper); fontTools covers fonts. Not on winget, so install them by hand on Windows if you need them: resvg, rsvg-convert, FluidSynth, abcMIDI, Csound, Faust, basisu and COLMAP. Sonic Pi needs version 5 (Linux distributions package older ones; get it from [sonic-pi.net](https://sonic-pi.net)).

## Recipes, styles, policy and the library

**Recipes** are TOML files in [`recipes/`](recipes) (and `<project>/.aeneas/recipes/`): inputs, then steps that refer to earlier results (`{concept.path}`). Each run writes its files and a `manifest.json` into one folder. `prop` makes a game-ready model: the best of several concept images on white, TRELLIS.2, then Blender sets the real size, puts the origin at the bottom centre, decimates to 20,000 faces and exports LODs at 50 % and 25 %.

**Style packs** are folders with a `style.toml` in [`styles/`](styles) or `<project>/.aeneas/styles/`: prompt prefix and suffix, negative prompt, preferred model, reference images (used with FLUX.2 klein), LoRAs (applied by stable-diffusion.cpp) and a palette. `--style storybook` on any image or sound command applies it.

**Licence policy**: `aen policy init` writes `.aeneas/policy.toml` in a project: the allowed licences (default CC0, MIT, Apache-2.0, OFL, CC BY, BSD-3, public domain), `allow_models` and `deny_models`. Generation and library imports check it; TRELLIS.2 is refused there until you allow it, because of DINOv3.

**Asset library** (`~/.aeneas/library.db`): every generated file is added automatically. Index a downloaded pack where it is, with its licence:

```bash
aen library import ~/projects/game/assets/kenney --source Kenney --licence CC0 --url https://kenney.nl
aen library search "mossy stone" --licence CC0
aen library credits ~/projects/game --write CREDITS.md
```

## ComfyUI as an engine and a playground

```bash
make comfyui        # ComfyUI v0.40.0 + ComfyUI-GGUF, pinned; reads models/ in place (no copies)
make comfyui-run    # http://127.0.0.1:8188
```

ComfyUI uses the same GGUF files as `sd-cli`. The factory ships a small ComfyUI node, `AeneasUnetLoaderGGUF`, so ComfyUI can read stable-diffusion.cpp's GGUF layout. `comfy_image` runs the factory's workflows ([`aeneas/comfy_workflows`](aeneas/comfy_workflows)) through ComfyUI's API with the same checks and provenance as every other engine; the workflow graph goes into the record.

## What it installs

<!-- models:start -->
| Model | Group | Size | Does | Licence | Source |
|---|---|---|---|---|---|
| Z-Image Turbo | image | 11.2 GB | Fast text-to-image (8 steps), photographic and illustrative; Q8 GGUF with a Qwen3-4B text encoder | Apache-2.0. | [huggingface.co/Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) |
| FLUX.2 [klein] 4B | image | 4.5 GB | Text-to-image and editing from reference images (4 steps); Q8 GGUF, shares the Qwen3-4B text encoder of z-image-turbo | Apache-2.0. | [huggingface.co/black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) |
| TRELLIS.2 4B | 3d | 16.5 GB | One image to a textured, UV-unwrapped GLB with PBR maps; GGUF set with DINOv3 features and BiRefNet matting | MIT (TRELLIS.2, BiRefNet); DINOv3 License (Meta) for dinov3.gguf. Download needs `ACCEPT=dinov3`. | [huggingface.co/microsoft/TRELLIS.2-4B](https://huggingface.co/microsoft/TRELLIS.2-4B) |
| MOSS-SoundEffect v2.0 (MLX bf16) | sound, Apple Silicon | 8.4 GB | Sound effects, foley and ambience from a description; 48 kHz, up to 30 s | Apache-2.0. | [huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0) |
| MOSS-SoundEffect v2.0 (GGUF BF16, openmoss) | sound, Linux, Windows, Intel Macs | 7.1 GB | Sound effects, foley and ambience from a description; 48 kHz, up to 30 s. The same model as moss-sfx, for the openmoss C++ runtime (CUDA, Vulkan, ROCm or CPU) | Apache-2.0. | [huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0) |
| Real-ESRGAN x4plus | upscale (optional) | 67 MB | Four times larger images, general photos and renders | BSD-3-Clause. | [github.com/xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) |
| BiRefNet general lite (ONNX, for rembg) | matte (optional) | 224 MB | Background removal: the subject on a transparent background | MIT. | [github.com/ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) |
| SigLIP base, patch 16, 224 px | scoring (optional) | 816 MB | Scores how well an image matches its prompt; image search by meaning | Apache-2.0. | [huggingface.co/google/siglip-base-patch16-224](https://huggingface.co/google/siglip-base-patch16-224) |
| CLAP HTSAT (unfused) | scoring (optional) | 618 MB | Scores how well a sound matches its description | Apache-2.0. | [huggingface.co/laion/clap-htsat-unfused](https://huggingface.co/laion/clap-htsat-unfused) |
| Kokoro 82M (MLX bf16) | speech (optional), Apple Silicon | 330 MB | Text to speech, English voices; fast and small | Apache-2.0. | [huggingface.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |
| Kokoro 82M (PyTorch) | speech (optional), Linux, Windows, Intel Macs | 330 MB | Text to speech, English voices; fast and small, CPU is enough. The same model as kokoro-82m, for the kokoro PyTorch package | Apache-2.0. | [huggingface.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |
| GeneralUser GS 2.0.3 (SoundFont) | music (optional) | 32 MB | General MIDI instrument bank: turns MIDI into audio with FluidSynth (aen music) | GeneralUser GS License v2.0. | [github.com/mrbumpy409/GeneralUser-GS](https://github.com/mrbumpy409/GeneralUser-GS) |

The four core models total **40.5 GB** on Apple Silicon and **39.2 GB** on Linux and Windows (sound uses the GGUF variant there); the optional ones **2.1 GB** and **2.1 GB**. Each machine downloads only the variants for its platform. Every file's URL (pinned to a commit or release), size and SHA-256 are in [`models.json`](models.json).
<!-- models:end -->

| Tool | Pinned | Licence | Used for |
|---|---|---|---|
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | `59c23bc` | MIT | images, editing, tiles, upscaling |
| [trellis.cpp](https://github.com/pwilkin/trellis.cpp) | `2516c48` | MIT | 3D |
| [moss-soundeffect-mlx](https://github.com/xocialize/moss-soundeffect-mlx) | `4e8e3e3` | Apache-2.0 | sound effects on Apple Silicon |
| [openmoss](https://github.com/pwilkin/openmoss) | v0.3.0 (`bfb1f46`) | Apache-2.0 | sound effects elsewhere (moss-tts-cli) |
| [mlx-audio](https://github.com/Blaizzy/mlx-audio) | `requirements/speech.txt` | MIT | speech on Apple Silicon |
| [kokoro](https://github.com/hexgrad/kokoro) (PyTorch) | 0.9.4, `requirements/speech-torch.txt` | Apache-2.0 (its phonemizer and espeak-ng are GPL-3.0) | speech elsewhere |
| [rembg](https://github.com/danielgatis/rembg) | `requirements/matte.txt` | MIT | background removal |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | v0.40.0, `6ea2651` | GPL-3.0, Apache-2.0 | optional engine and UI |
| The explicit tools (`make explicit`) | [`Brewfile`](Brewfile), [`deps/`](deps), `requirements/explicit.txt`, [`requirements/explicit-node`](requirements/explicit-node), Yarn Spinner 3.2.2 | each its own (`aen tools list` shows them): mostly MIT, BSD, Apache-2.0, LGPL and GPL; none of them puts a licence on what you make | diagrams, SVG, music, synthesis, CAD, mesh work, levels, dialogue |

Every Python environment is locked with exact versions and hashes in [`requirements/`](requirements), and the Node packages in a lockfile.

## Requirements and timings

macOS on Apple Silicon, Linux on x64, or Windows on x64, with a C++ compiler, CMake, git and [uv](https://docs.astral.sh/uv/) (see Quick start), and ffmpeg and Blender for sound mastering, 3D previews and clean-up. `make prereqs` (`py install.py prereqs`) checks, and names the GPU backend it will build for. A GPU with about 16 GB of memory runs everything; images also run on the CPU (slowly), 3D realistically needs a GPU. The explicit tools take about 5.5 GB on macOS (Sonic Pi is 364 MB of that): system packages and apps, and 2.6 GB of Python and Node environments in `tools/explicit`. Apps such as Blender, GIMP, Godot, Tiled and Sonic Pi are found where each OS installs them, or set `AEN_BLENDER`, `AEN_GIMP`, ... to their paths.

Measured on an Apple M5 Pro, 64 GB, macOS 27 (other machines: run `aen check` for your own numbers):

| Job | Time |
|---|---|
| Image, 1024 px (Z-Image, 8 steps) | about 2 to 3 minutes; most of it is the VAE decode, kept on the CPU because the Metal decode gives blank images with this build |
| Image, 512 px, 4 steps; three candidates ranked by prompt match | about 20 s each; 75 s for all three |
| Image through ComfyUI, 512 px, 8 steps | 41 s |
| 3D, res 512 / res 1024 | about 5 minutes / about 24 minutes |
| Sound effect, 2 s at 10 steps / 5 s at 100 steps | 19 s / about 2 minutes |
| Speech, one sentence | about 8 s |
| Building the three core tools from a clean clone | 6.5 minutes |
| Diagram (D2), SVG icon, or a 20 s tune from ABC, mastered | 1 to 2.5 s each, mostly starting Python |

The sound model needs about 14 GB of GPU memory; the service unloads it after five idle minutes.

## Resources and start-up

| Part | Runs | Idle cost (measured) |
|---|---|---|
| MCP server (`aen mcp`) | one per agent app or session, started and stopped by that app | 15 MB, no CPU |
| Factory service | at login if `aen service autostart on` (stays running); otherwise from the first tool call, stopping after 30 idle minutes | 42 MB, no CPU |
| Scoring worker (SigLIP, CLAP) | from the first ranking or search by meaning; exits after 5 idle minutes | about 400 MB while loaded, then nothing |
| Sound model worker (MOSS) | from the first sound job; exits after 5 idle minutes | about 14 GB of GPU memory while loaded |
| Image and 3D tools | only while a job runs | about 10 GB (images), 16 GB or more (3D) during the job |

```bash
aen service autostart on     # start the service at login (LaunchAgent, systemd user unit, or Windows Run entry); "off" removes it
aen service status           # pid, idle time, which models are loaded
```

## Security

The service listens on 127.0.0.1 only. Every request needs the token in `~/.aeneas/service.json`, which only you can read. Requests with a browser `Origin` header, or a `Host` other than localhost, are refused, so web pages cannot drive it. It runs only the factory's own operations and recipes, reads inputs and writes outputs only under your home folder and never inside the factory, and never downloads anything. Model downloads go through `aen models download`, which checks every file's SHA-256 against [`models.json`](models.json). The explicit tools that take text (diagrams, SVG, music, dialogue) run sandboxed (`sandbox-exec` on macOS, bubblewrap on Linux) with no network and writes only to a temporary folder beside the output; on Windows, which has no comparable sandbox, they run unsandboxed, since they read notation rather than run programs. Mermaid is the exception everywhere, since headless Chrome sandboxes itself and cannot run inside another sandbox. Sonic Pi code is a Ruby program rather than notation, so it gets a tighter sandbox: network only on this machine's loopback (Sonic Pi's own parts talk over it; on Linux a private loopback of its own), and nothing under your home folder can be read except its scratch folder, so it cannot read the service token, keys or documents. Without a sandbox (Windows, or Linux without bubblewrap) it is refused. It runs with its own Sonic Pi home, never your `~/.sonic-pi`, and its mixer is muted, so nothing is played aloud. `aen tool` runs whatever you give it, as you, so pass `--sandbox DIR` for code you did not write. One scoring model (CLAP) exists only as a PyTorch pickle; it is pinned by SHA-256 and loaded with weights-only loading.

## Development

```bash
make test           # 54 tests, no models or GPU needed
make vscode-test    # the editor extension: unit tests, then integration tests in a real VS Code
python scripts/gen_docs.py --check    # the docs agree with models.json
.venv/bin/python scripts/mcp_smoke.py ~/some/project    # the MCP path end to end
```

CI ([`.github/workflows`](.github/workflows)) runs only on the owner's self-hosted Linux runner, never on GitHub-hosted (billed) runners: the tests, the docs check and the editor extension on every push to `main`, a weekly check that every pinned download still answers, and on request (*Run workflow*) a build of the engines and the extension's integration tests. Because the repository is public and the runner is a private machine, no workflow runs for pull requests, the token is read-only, only GitHub's own actions are used (pinned to commits), and nothing is fetched from Git LFS. In a fork, register your own runner or run the checks above locally. The design and its reasons are in [`docs/design.md`](docs/design.md).

## Troubleshooting

- **A step failed its checks**: the error says why (blank, seam, silent). Try another seed or `--candidates 3`.
- **Out of memory**: use `--size 768` or less for images and `--res 512` for 3D; the sound model alone takes about 14 GB.
- **A download stopped**: run the same command again; it resumes and checks each file.
- **Something broke after an OS, driver or package-manager update**: `aen check --quick` shows what, `make clean-tools tools` rebuilds.
- **Slow images or 3D**: `aen check --quick` names the GPU backend; `cpu` means no CUDA toolkit or Vulkan SDK was found when building. Install one, then `make clean-tools tools` (or `AEN_GPU=vulkan make sd trellis moss`).
- **An explicit tool fails**: `aen tools check NAME` shows what is wrong; `make explicit` installs anything missing.
- Each output's `.log` holds the tool's own output.

## Licences

The code and documents here are under the [MIT License](LICENSE), and so are the gallery images. Tools and models keep their own licences (tables above; per file in `models.json`). Z-Image Turbo, Qwen3-4B, FLUX.2 [klein] 4B, MOSS-SoundEffect and Kokoro are Apache-2.0 (on Linux and Windows, Kokoro's English phonemizer and the espeak-ng it bundles are GPL-3.0 tools; that covers the tools, not the speech you make); TRELLIS.2, BiRefNet and Real-ESRGAN are MIT or BSD. **TRELLIS.2's `dinov3.gguf` is under Meta's [DINOv3 License](https://ai.meta.com/resources/models-and-libraries/dinov3-license)**, so it downloads only with `ACCEPT=dinov3`. Using it counts as accepting that licence: commercial use is allowed; where DINOv3 or its derivatives are distributed, "Built with DINOv3" must be shown prominently with a copy of the licence; military, weapons and espionage uses and use by parties under trade controls are forbidden. 3D models made by this factory record "Built with DINOv3" in their provenance and credits; the gallery's 3D models are built with DINOv3. Scoring uses SigLIP rather than OpenAI's CLIP, whose model card puts any deployed use out of scope. Music rendered with the GeneralUser GS SoundFont may be used freely, commercially too (its licence, v2.0, covers the music made with it). Sonic Pi is MIT, its SuperSonic engine builds on SuperCollider (GPL-3.0), and the samples it ships are CC0 (from freesound.org), so Sonic Pi renders are yours to use. The explicit tools keep their own licences, several of them GPL or LGPL; that applies to the tools, not to the files you make with them. The 9B FLUX.2 klein models are non-commercial; this repository uses only the 4B one. Every record says what a model card states, which is not legal advice: whether you may use a generated file depends on where it goes.

## Credits

Built on [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp), [trellis.cpp](https://github.com/pwilkin/trellis.cpp), [openmoss](https://github.com/pwilkin/openmoss), [moss-soundeffect-mlx](https://github.com/xocialize/moss-soundeffect-mlx), [MLX](https://github.com/ml-explore/mlx), [mlx-audio](https://github.com/Blaizzy/mlx-audio), [kokoro](https://github.com/hexgrad/kokoro), [PyTorch](https://pytorch.org/), [bubblewrap](https://github.com/containers/bubblewrap), [rembg](https://github.com/danielgatis/rembg), [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF), the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), and the model authors: Tongyi-MAI (Z-Image), Black Forest Labs (FLUX.2), Microsoft (TRELLIS.2), Meta (DINOv3), the BiRefNet authors, Qwen, OpenMOSS, hexgrad (Kokoro), Xintao Wang (Real-ESRGAN), Google (SigLIP) and LAION (CLAP). Thanks also to the GGUF and MLX converters: leejet, unsloth, ilintar (Piotr Wilkin, also of trellis.cpp and openmoss) and mlx-community.

The explicit tools: [ImageMagick](https://imagemagick.org/), [resvg](https://github.com/linebender/resvg), [librsvg](https://gitlab.gnome.org/GNOME/librsvg), [OpenCV](https://opencv.org/), [vtracer](https://github.com/visioncortex/vtracer), [coloraide](https://github.com/facelessuser/coloraide), [fontTools](https://github.com/fonttools/fonttools), [Graphviz](https://graphviz.org/), [D2](https://d2lang.com/), [Mermaid](https://mermaid.js.org/), [Vega-Lite](https://vega.github.io/vega-lite/), [abcMIDI](https://github.com/sshlien/abcmidi), [music21](https://github.com/cuthbertLab/music21), [pretty_midi](https://github.com/craffel/pretty-midi), [mido](https://github.com/mido/mido), [LilyPond](https://lilypond.org/), [FluidSynth](https://www.fluidsynth.org/) with [GeneralUser GS](https://github.com/mrbumpy409/GeneralUser-GS) by S. Christian Collins, [Csound](https://csound.com/), [SuperCollider](https://supercollider.github.io/), [Faust](https://faust.grame.fr/), [SoX](https://sourceforge.net/projects/sox/), [pedalboard](https://github.com/spotify/pedalboard), [moderngl](https://github.com/moderngl/moderngl), [opensimplex](https://github.com/lmas/opensimplex), [Taichi](https://www.taichi-lang.org/), [OpenSCAD](https://openscad.org/), [build123d](https://github.com/gumyr/build123d), [trimesh](https://github.com/mikedh/trimesh), [xatlas](https://github.com/jpcy/xatlas), [PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab), [meshoptimizer/gltfpack](https://github.com/zeux/meshoptimizer), [glTF-Validator](https://github.com/KhronosGroup/glTF-Validator), [Basis Universal](https://github.com/BinomialLLC/basis_universal), [COLMAP](https://colmap.github.io/), [Blender](https://www.blender.org/), [pymunk](https://www.pymunk.org/), [MuJoCo](https://mujoco.org/), [Manim](https://www.manim.community/), [Tiled](https://www.mapeditor.org/), [Godot](https://godotengine.org/), [Ink](https://www.inklestudios.com/ink/) and [inkjs](https://github.com/y-lohse/inkjs) (inkle), [Yarn Spinner](https://www.yarnspinner.dev/), and [Sonic Pi](https://sonic-pi.net/) by Sam Aaron, with its CC0 samples from [freesound.org](https://freesound.org/).
