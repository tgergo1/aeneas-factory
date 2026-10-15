# Aeneas Factory

**Local generation of images, textures, 3D models, sound effects and speech on a Mac, built so that AI agents can use it safely and every result can be trusted.** Open models, pinned and checksummed. One shared service with a job queue. An MCP server for Claude Code and Codex. Automatic checks so a blank image is never reported as a success. Provenance written into every file. A licence policy per project. Recipes that turn a request into a finished asset. A searchable library of everything made or downloaded.

**Built with DINOv3**: the 3D generator (TRELLIS.2) uses Meta's DINOv3 image features under the [DINOv3 License](https://ai.meta.com/resources/models-and-libraries/dinov3-license); see [Licences](#licences).

<p align="center">
  <img src="docs/factory.svg" alt="Diagram: agents use the MCP server, scripts the aen command line, people ComfyUI and Blender. All work goes through one factory service: licence policy, engine, checks, ranked candidates, provenance, asset library. Engines: stable-diffusion.cpp (Z-Image Turbo, FLUX.2 klein), trellis.cpp (TRELLIS.2), MLX (MOSS-SoundEffect, Kokoro), Real-ESRGAN, BiRefNet, ComfyUI, Blender, ffmpeg." width="100%">
</p>

## What it does

| | |
|---|---|
| **Generate** | Images from text (Z-Image Turbo, FLUX.2 [klein] 4B), image editing from references, seamless textures with PBR maps, textured 3D models from one image (TRELLIS.2), sound effects (MOSS-SoundEffect), speech (Kokoro), 4x upscaling (Real-ESRGAN), background removal (BiRefNet) |
| **Check** | Every output is checked before it counts: blank or flat images, visible seams in tiles, silent audio, empty or flat meshes. A failure is an error, never a result |
| **Choose** | `--candidates N` makes several, drops the failures, ranks the rest by how well they match the prompt (SigLIP for images, CLAP for sound) and keeps the best, recording all of them |
| **Record** | Provenance inside the file (PNG text, glTF `extras`, WAV `INFO`) and beside it (`<file>.json`): the models with every file's SHA-256, the factory and tool versions, prompt, seed, settings, checks and the licence policy that applied |
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

### Recipes: finished assets, not raw generations

These came out of one command each, through the factory service, with every intermediate step and its provenance kept ([`docs/gallery/recipes`](docs/gallery/recipes)).

| | | |
|---|---|---|
| <img src="docs/gallery/recipes/bucket-render.png" width="100%" alt="A game-ready wooden bucket model"> | <img src="docs/gallery/recipes/oak-2x2.png" width="100%" alt="An oak plank texture tiled 2x2"> | <img src="docs/gallery/recipes/key.png" width="100%" alt="A golden key on a transparent background"> |
| **`prop`**: best of 2 concept images → TRELLIS.2 → Blender: 0.4 m tall, origin at the bottom, 149,556 faces cut to LODs of 20,000 / 10,000 / 5,000 ([`bucket.glb`](docs/gallery/recipes/bucket.glb), [manifest](docs/gallery/recipes/bucket-manifest.json)). 11.6 minutes | **`texture`**: best of 2 tiles by prompt match, seam checked (edge jump 0.53x the texture's own detail), plus height, [normal](docs/gallery/recipes/oak-normal.png), roughness and AO maps | **`sprite`**: best of 2 images, cut out onto transparency with BiRefNet |

<img src="docs/gallery/recipes/door-wave.png" width="100%" alt="Waveform of the generated door sound">

**`sfx`**: two takes ranked by CLAP, silence trimmed, loudness normalised to -18 LUFS with a -1 dBTP peak: [`door.wav`](docs/gallery/recipes/door.wav)

## Quick start

```bash
brew install cmake uv git-lfs ffmpeg      # and the Xcode Command Line Tools: xcode-select --install
git clone https://github.com/tgergo1/aeneas-factory.git
cd aeneas-factory
make install GROUPS=image                 # images only: tools + 15.7 GB of models + a quick check
```

Everything (all four core models, 40.5 GB; read the [DINOv3 licence](https://ai.meta.com/resources/models-and-libraries/dinov3-license) first, since TRELLIS.2 needs it):

```bash
make install ACCEPT=dinov3
make extras models-extras                 # optional: ranking, background removal, speech, upscaling (2.1 GB)
```

Then:

```bash
export PATH="$PWD/bin:$PATH"
aen image "a lighthouse on a cliff at dawn, watercolour" -o lighthouse.png --candidates 3
aen texture "weathered oak planks" -o oak.png
aen recipe prop --out-dir props subject="a wooden water bucket with iron hoops" size_m=0.4
aen sfx "rain on a tin roof, distant thunder" --seconds 10 -o rain.wav
aen speech "Welcome to the village." -o welcome.wav --voice bm_george
```

## Using it from an AI agent

Register the MCP server once; it starts the factory service by itself when needed:

```bash
claude mcp add --scope user aeneas -- "$PWD/bin/aen" mcp
codex mcp add aeneas -- "$PWD/bin/aen" mcp
```

Tools: `capabilities`, `generate_image`, `edit_image`, `make_texture`, `image_to_3d`, `generate_sound`, `generate_speech`, `upscale_image`, `remove_background`, `run_recipe`, `job_status`, `cancel_job`, `list_jobs`, `search_assets`, `get_provenance`, `project_credits`.

- Every finished result comes back with a **thumbnail the agent can look at**: the image, a 2x2 tile preview, a render of the 3D model, or a waveform. Candidates come back as a contact sheet.
- Long work (3D takes minutes) returns a **job id at once**; `job_status` waits for it.
- Outputs go to `<project_dir>/generated/`. The server **never runs code it is sent, never downloads models, and writes only under your home folder, outside the factory**.
- [`AGENTS.md`](AGENTS.md) tells agents how to use all this, plus Blender, GIMP and free asset libraries, with the licence rules. `scripts/mcp_smoke.py` tests the whole path the way an agent uses it.

## The command line

`aen <command> --help` for every option. `ai-image`, `ai-3d`, `ai-sfx`, … are short for `aen image`, `aen 3d`, `aen sfx`, … When the factory service is running, commands queue there (nothing fights over the GPU); `--local` runs them in the calling process.

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
| MOSS-SoundEffect v2.0 (MLX bf16) | sound | 8.4 GB | Sound effects, foley and ambience from a description; 48 kHz, up to 30 s | Apache-2.0. | [huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0) |
| Real-ESRGAN x4plus | upscale (optional) | 67 MB | Four times larger images, general photos and renders | BSD-3-Clause. | [github.com/xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) |
| BiRefNet general lite (ONNX, for rembg) | matte (optional) | 224 MB | Background removal: the subject on a transparent background | MIT. | [github.com/ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet) |
| SigLIP base, patch 16, 224 px | scoring (optional) | 816 MB | Scores how well an image matches its prompt; image search by meaning | Apache-2.0. | [huggingface.co/google/siglip-base-patch16-224](https://huggingface.co/google/siglip-base-patch16-224) |
| CLAP HTSAT (unfused) | scoring (optional) | 618 MB | Scores how well a sound matches its description | Apache-2.0. | [huggingface.co/laion/clap-htsat-unfused](https://huggingface.co/laion/clap-htsat-unfused) |
| Kokoro 82M (MLX bf16) | speech (optional) | 330 MB | Text to speech, English voices; fast and small | Apache-2.0. | [huggingface.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |

The four core models total **40.5 GB**; the optional ones **2.1 GB**. Every file's URL (pinned to a commit or release), size and SHA-256 are in [`models.json`](models.json).
<!-- models:end -->

| Tool | Pinned | Licence | Used for |
|---|---|---|---|
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | `59c23bc` | MIT | images, editing, tiles, upscaling |
| [trellis.cpp](https://github.com/pwilkin/trellis.cpp) | `2516c48` | MIT | 3D |
| [moss-soundeffect-mlx](https://github.com/xocialize/moss-soundeffect-mlx) | `4e8e3e3` | Apache-2.0 | sound effects |
| [mlx-audio](https://github.com/Blaizzy/mlx-audio) | `requirements/speech.txt` | MIT | speech |
| [rembg](https://github.com/danielgatis/rembg) | `requirements/matte.txt` | MIT | background removal |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | v0.40.0, `6ea2651` | GPL-3.0, Apache-2.0 | optional engine and UI |

Every Python environment is locked with exact versions and hashes in [`requirements/`](requirements).

## Requirements and timings

A Mac with Apple Silicon (tested: M5 Pro, 64 GB, macOS 27). Xcode Command Line Tools, Homebrew `cmake`, `uv`, `git`; `ffmpeg` and Blender for sound mastering, 3D previews and clean-up. `make prereqs` checks.

Measured on the M5 Pro:

| Job | Time |
|---|---|
| Image, 1024 px (Z-Image, 8 steps) | about 2 to 3 minutes; most of it is the VAE decode, kept on the CPU because the Metal decode gives blank images with this build |
| Image, 512 px, 4 steps; three candidates ranked by prompt match | about 20 s each; 75 s for all three |
| Image through ComfyUI, 512 px, 8 steps | 41 s |
| 3D, res 512 / res 1024 | about 5 minutes / about 24 minutes |
| Sound effect, 2 s at 10 steps / 5 s at 100 steps | 19 s / about 2 minutes |
| Speech, one sentence | about 8 s |
| Building the three core tools from a clean clone | 6.5 minutes |

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
aen service autostart on     # start the service at login (a LaunchAgent); "off" to remove it
aen service status           # pid, idle time, which models are loaded
```

## Security

The service listens on 127.0.0.1 only. Every request needs the token in `~/.aeneas/service.json`, which only you can read. Requests with a browser `Origin` header, or a `Host` other than localhost, are refused, so web pages cannot drive it. It runs only the factory's own operations and recipes, reads inputs and writes outputs only under your home folder and never inside the factory, and never downloads anything. Model downloads go through `aen models download`, which checks every file's SHA-256 against [`models.json`](models.json). One scoring model (CLAP) exists only as a PyTorch pickle; it is pinned by SHA-256 and loaded with weights-only loading.

## Development

```bash
make test           # 32 tests, no models or GPU needed
python scripts/gen_docs.py --check    # the docs agree with models.json
.venv/bin/python scripts/mcp_smoke.py ~/some/project    # the MCP path end to end
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the tests and the docs check on every push, checks every pinned download weekly, and builds the tools on an Apple Silicon runner on demand. The design and its reasons are in [`docs/design.md`](docs/design.md).

## Troubleshooting

- **A step failed its checks**: the error says why (blank, seam, silent). Try another seed or `--candidates 3`.
- **Out of memory**: use `--size 768` or less for images and `--res 512` for 3D; the sound model alone takes about 14 GB.
- **A download stopped**: run the same command again; it resumes and checks each file.
- **Something broke after a macOS or Homebrew update**: `aen check --quick` shows what, `make clean-tools tools` rebuilds.
- Each output's `.log` holds the tool's own output.

## Licences

The code and documents here are under the [MIT License](LICENSE), and so are the gallery images. Tools and models keep their own licences (tables above; per file in `models.json`). Z-Image Turbo, Qwen3-4B, FLUX.2 [klein] 4B, MOSS-SoundEffect and Kokoro are Apache-2.0; TRELLIS.2, BiRefNet and Real-ESRGAN are MIT or BSD. **TRELLIS.2's `dinov3.gguf` is under Meta's [DINOv3 License](https://ai.meta.com/resources/models-and-libraries/dinov3-license)**, so it downloads only with `ACCEPT=dinov3`. Using it counts as accepting that licence: commercial use is allowed; where DINOv3 or its derivatives are distributed, "Built with DINOv3" must be shown prominently with a copy of the licence; military, weapons and espionage uses and use by parties under trade controls are forbidden. 3D models made by this factory record "Built with DINOv3" in their provenance and credits; the gallery's 3D models are built with DINOv3. Scoring uses SigLIP rather than OpenAI's CLIP, whose model card puts any deployed use out of scope. The 9B FLUX.2 klein models are non-commercial; this repository uses only the 4B one. Every record says what a model card states, which is not legal advice: whether you may use a generated file depends on where it goes.

## Credits

Built on [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp), [trellis.cpp](https://github.com/pwilkin/trellis.cpp), [moss-soundeffect-mlx](https://github.com/xocialize/moss-soundeffect-mlx), [MLX](https://github.com/ml-explore/mlx), [mlx-audio](https://github.com/Blaizzy/mlx-audio), [rembg](https://github.com/danielgatis/rembg), [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF), the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), and the model authors: Tongyi-MAI (Z-Image), Black Forest Labs (FLUX.2), Microsoft (TRELLIS.2), Meta (DINOv3), the BiRefNet authors, Qwen, OpenMOSS, hexgrad (Kokoro), Xintao Wang (Real-ESRGAN), Google (SigLIP) and LAION (CLAP). Thanks also to the GGUF and MLX converters: leejet, unsloth, ilintar and mlx-community.
