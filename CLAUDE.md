# Aeneas Factory

Local generators for images, textures, 3D models, sound effects and speech, explicit tools (code and text in, exact assets out), with an MCP server, a job service, checks, provenance, licence policy, recipes and an asset library. `README.md` explains setup, `docs/design.md` the design; the notes for agents are below.

When working on this repository: `make test` (no models needed) and `python scripts/gen_docs.py --check` must pass, and `make vscode-test` when `editors/vscode` or the service changes; real runs go through `bin/aen` (e.g. `bin/aen check`). Never commit `models/`, `tools/` or `.venv/`. CI runs only on the owner's self-hosted Linux runner (owner's request, 2026-10-21): never add GitHub-hosted runners or any other billable Actions feature (larger runners, artifacts, LFS in CI), never add pull_request triggers (the repo is public and the runner is a private machine), and keep the checks runnable locally. The code must work on macOS, Linux and Windows: put OS differences in aeneas/host.py, not in callers.

@AGENTS.md
