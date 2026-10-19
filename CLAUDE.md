# Aeneas Factory

Local generators for images, textures, 3D models, sound effects and speech, explicit tools (code and text in, exact assets out), with an MCP server, a job service, checks, provenance, licence policy, recipes and an asset library. `README.md` explains setup, `docs/design.md` the design; the notes for agents are below.

When working on this repository: `make test` (no models needed) and `python scripts/gen_docs.py --check` must pass, and `make vscode-test` when `editors/vscode` or the service changes; real runs go through `bin/aen` (e.g. `bin/aen check`). Never commit `models/`, `tools/` or `.venv/`.

@AGENTS.md
