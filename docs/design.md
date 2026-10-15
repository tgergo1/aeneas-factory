# Design

How Aeneas Factory is put together, and why. The README says how to use it.

## Goals

1. **Local and open.** Everything runs on one Mac with open-licensed models; nothing leaves the machine after the downloads.
2. **Safe for agents.** An AI agent can generate assets without being able to run arbitrary code, fetch models, or write outside the project it works on.
3. **Trustworthy results.** A failure is never reported as a success, and every file says how it was made, from what, under which licence.
4. **Reproducible.** Tools, models and Python packages are pinned; a record pins the exact versions and seeds behind each file.
5. **Finished assets, not raw generations.** Most of the work is between the model and something a game or project can use: choosing, cleaning up, sizing, mastering, crediting.

## Layers

```
ways in      MCP server (agents) · aen command line (scripts, people) · ComfyUI and Blender (people)
service      one per machine: job queue, policy, engines, checks, candidates, provenance, library
engines      sd-cli · trellis-cli · MOSS worker (MLX) · Kokoro (MLX) · rembg · ComfyUI · Blender · ffmpeg
stores       models.json + models/ · ~/.aeneas/library.db · recipes/ · styles/ · <project>/.aeneas/
```

All three ways in end in the same function calls (`aeneas/ops.py`), so policy, checks, provenance and the library apply the same everywhere.

## Decisions

**One service, one queue.** Claude Code and Codex each start their own MCP server process; without a shared service, two agents would start two GPU jobs at once and run out of memory. The service runs one job at a time and the MCP servers are thin clients. The command line uses it too when it is running (`--local` to bypass).

**Keeping models loaded only where it pays.** Measured: an `sd-cli` image spends about 6 s of 110 s loading, the rest sampling and decoding, so a resident image server would save little and pin about 10 GB. The sound model is different, so it runs in a persistent MLX worker that unloads after five idle minutes.

**Checks before success.** The Metal VAE decode of this stable-diffusion.cpp build returns blank white images (checked again 2026-10-15), and the first version of this repository reported them as successes. Every output now passes a check for its kind: image spread, tile seams, audio level, mesh vertex count and extent, cut-out coverage.

**Candidates and ranking.** Single generations are the weakest link. `--candidates N` uses consecutive seeds, drops failures, and ranks by SigLIP (images) or CLAP (sound) similarity to the prompt when the scoring models are installed; otherwise the first that passes wins. All candidates stay on disk and in the record.

**Provenance inside and beside the file.** A sidecar is easy to lose, an embedded record survives copying. PNG gets an `iTXt` chunk, GLB an `asset.extras` entry, WAV a `LIST/INFO` comment. The sidecar adds the final file's SHA-256 (the embedded copy cannot contain its own hash). Records list each model file's SHA-256 and URL and the git commit of every tool and of the factory.

**Licence policy per project, acceptance per user.** A project decides which licences it allows (`.aeneas/policy.toml`); a user accepts licences that ask for agreement once (`~/.aeneas/accepted.json`). TRELLIS.2's DINOv3 features are gated by Meta on Hugging Face; the GGUF conversion is ungated, so the factory asks for acceptance itself instead of silently skipping Meta's step.

**Recipes as data.** TOML recipes are reviewable and versioned; a run's `manifest.json` records every step's arguments and results. Placeholders refer to inputs and earlier step results; nothing in a recipe is executed as code.

**ComfyUI as an engine, not the core.** ComfyUI changes often and custom nodes break, so the factory's core does not depend on it. It is an optional engine and a place for people to explore, reading the same model files: the factory's `AeneasUnetLoaderGGUF` node reshapes the two pad tokens that differ between stable-diffusion.cpp's and ComfyUI's GGUF layouts, so one 6.6 GB file serves both.

**Scoring models.** Image ranking and search use SigLIP (Apache-2.0, safetensors), whose card names image-text retrieval as an intended use; OpenAI's CLIP was used first and replaced because its card puts any deployed use out of scope. CLAP (Apache-2.0) ranks sound; it is only published as a PyTorch pickle, so it is pinned by SHA-256 and loaded with weights-only loading. Scoring only ranks candidates and never shapes the output.

**DINOv3 attribution.** TRELLIS.2's features come from DINOv3, whose licence requires "Built with DINOv3" where DINOv3 or derivatives are distributed. The register carries the attribution; every 3D record and credits page repeats it; the README shows it.

## Security model

- The service binds 127.0.0.1 and requires a random token from a file only the user can read.
- It refuses requests with an `Origin` header or a non-localhost `Host`, which stops web pages (including DNS rebinding) from driving it.
- It runs only registered operations and recipes; arguments are data. Input files must exist under the user's home folder; outputs must be under it and outside the factory.
- It never downloads. Models arrive only through `aen models download`, which checks SHA-256 against the register.
- Workers speak a fixed JSON protocol (the MOSS worker evaluates no code).
- The MCP server exposes generation, status, search and provenance only: no shell, no file reading beyond provenance, no downloads.

## Measured on an M5 Pro, 64 GB

| Job | Time |
|---|---|
| sd-cli image 1024 px, 8 steps | 110 s: load 6 s, sampling 67 s, VAE decode on CPU 40 s |
| Same with the Metal VAE decode | 77 s, but blank |
| Three 512 px candidates ranked by prompt match | 75 s |
| ComfyUI image 512 px, 8 steps | 41 s |
| TRELLIS.2 res 512 / 1024 | about 5 min / 24 min |
| MOSS 2 s at 10 steps / 5 s at 100 steps | 19 s / about 2 min |
| Kokoro speech, one sentence | 8 s |
| Clean build of the three core tools | 6.5 min |

## Not done, and why

- **C2PA content credentials**: they need signing certificates and `c2patool`; the embedded record covers the facts, and C2PA can be added on export when a project needs it.
- **LoRA training**: applying LoRAs works (style packs), but training them for Z-Image or FLUX.2 klein on Apple Silicon was not verified.
- **Video**: Wan 2.2 TI2V 5B is 24 GB and no project here needs it yet.
- **Linux and NVIDIA**: sd.cpp and trellis.cpp build there with `CMAKE_ARGS`, and ComfyUI is the natural engine; the MLX parts (sound, speech) are Apple-only. Untested.
