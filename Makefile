# Aeneas Factory: build the tools, download the models, check that everything works.
# `make help` lists the targets. Everything lands inside this folder (.venv/, tools/, models/).

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Pinned upstream sources: the exact commits this repository was tested with.
SD_REPO        := https://github.com/leejet/stable-diffusion.cpp
SD_COMMIT      := 59c23bce0d82be3a922023ab811194f05b3e2faa
TRELLIS_REPO   := https://github.com/pwilkin/trellis.cpp
TRELLIS_COMMIT := 2516c48b677050c570f47eba2e68dc8a5bc918b0
MOSS_REPO      := https://github.com/xocialize/moss-soundeffect-mlx.git
MOSS_COMMIT    := 4e8e3e36d4d9c991d16a3e65a4b7099d406b9ed8
COMFY_REPO     := https://github.com/Comfy-Org/ComfyUI.git
COMFY_COMMIT   := 3541246a9c997f4b8c32f9f88f3c985d02021c79  # v0.40.0
COMFY_GGUF_REPO   := https://github.com/city96/ComfyUI-GGUF.git
COMFY_GGUF_COMMIT := 6ea2651e7df66d7585f6ffee804b20e92fb38b8a
PYTHON_VERSION ?= 3.12

# What `make install` downloads: all (the four core models), or groups/ids, e.g. GROUPS="image sound".
GROUPS ?= all
# Licences you accept for downloads that ask for it, e.g. ACCEPT=dinov3 (TRELLIS.2's image features).
ACCEPT ?=

JOBS        ?= $(shell sysctl -n hw.ncpu 2>/dev/null || nproc)
CMAKE_ARGS  ?=
AEN         := bin/aen
SD_STAMP      := tools/.sd-$(SD_COMMIT)
TRELLIS_STAMP := tools/.trellis-$(TRELLIS_COMMIT)
MOSS_STAMP    := tools/.moss-$(MOSS_COMMIT)
ACCEPT_FLAGS  := $(foreach a,$(ACCEPT),--accept $(a))

.PHONY: help install all prereqs factory tools sd trellis moss scoring matte speech comfyui comfyui-run \
        models models-image models-3d models-sound models-scoring models-upscale models-matte models-speech \
        models-extras extras explicit check check-quick verify list test service-start service-stop autostart autostart-off mcp-info \
        vscode vscode-install vscode-test clean-tools distclean

help: ## Show this list
	@echo "Aeneas Factory: local images, textures, 3D models, sound and speech on Apple Silicon."
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'
	@echo
	@echo "Start with: make install GROUPS=image   (images only, 15.7 GB)  or  make install  (all four, 40.5 GB)"

install: prereqs factory tools models check-quick ## Everything for GROUPS (default all): prereqs, env, tools, models, quick check
all: install

prereqs: ## Check that the build prerequisites are installed
	@ok=1; \
	[ "$$(uname -s)/$$(uname -m)" = "Darwin/arm64" ] || { echo "WARN  not macOS on Apple Silicon: sd-cli and trellis-cli need CMAKE_ARGS for your GPU, and sound and speech (MLX) will not run"; }; \
	xcode-select -p >/dev/null 2>&1 || { echo "MISS  Xcode Command Line Tools: xcode-select --install"; ok=0; }; \
	for c in git cmake curl uv; do command -v $$c >/dev/null || { echo "MISS  $$c: brew install $$c"; ok=0; }; done; \
	command -v ffmpeg >/dev/null || echo "INFO  ffmpeg not found: sound mastering needs it (brew install ffmpeg)"; \
	[ -x /Applications/Blender.app/Contents/MacOS/Blender ] || command -v blender >/dev/null || echo "INFO  Blender not found: 3D previews and clean-up need it"; \
	free=$$(df -k . | awk 'NR==2 {print int($$4/1048576)}'); \
	[ $$free -ge 20 ] || echo "WARN  $$free GB free here; images need about 17 GB, everything about 45 GB"; \
	[ $$ok = 1 ] && echo "prerequisites ok ($$free GB free)" || { echo "install the missing tools above, then run make again"; exit 1; }

factory: .venv/.stamp ## The factory's own Python env (commands, service, MCP server)
.venv/.stamp: requirements/factory.txt
	uv venv --quiet --allow-existing --python $(PYTHON_VERSION) .venv
	uv pip install --quiet --python .venv/bin/python --require-hashes -r requirements/factory.txt
	@touch $@

tools: sd trellis moss ## Build the three core tools

sd: $(SD_STAMP) ## Build stable-diffusion.cpp (sd-cli, Metal)
$(SD_STAMP):
	@[ -d tools/stable-diffusion.cpp/.git ] || git clone --filter=blob:none $(SD_REPO) tools/stable-diffusion.cpp
	git -C tools/stable-diffusion.cpp fetch --quiet origin $(SD_COMMIT) || true
	git -C tools/stable-diffusion.cpp checkout --quiet $(SD_COMMIT)
	git -C tools/stable-diffusion.cpp submodule update --init --recursive --quiet
	cmake -S tools/stable-diffusion.cpp -B tools/stable-diffusion.cpp/build -DCMAKE_BUILD_TYPE=Release -DSD_METAL=ON $(CMAKE_ARGS)
	cmake --build tools/stable-diffusion.cpp/build --config Release --target sd-cli -j $(JOBS)
	@rm -f tools/.sd-*; touch $@

trellis: $(TRELLIS_STAMP) ## Build trellis.cpp (trellis-cli, Metal)
$(TRELLIS_STAMP):
	@[ -d tools/trellis.cpp/.git ] || git clone --filter=blob:none $(TRELLIS_REPO) tools/trellis.cpp
	git -C tools/trellis.cpp fetch --quiet origin $(TRELLIS_COMMIT) || true
	git -C tools/trellis.cpp checkout --quiet $(TRELLIS_COMMIT)
	git -C tools/trellis.cpp submodule update --init --recursive --quiet
	cmake -S tools/trellis.cpp -B tools/trellis.cpp/build -DCMAKE_BUILD_TYPE=Release $(CMAKE_ARGS)
	cmake --build tools/trellis.cpp/build --config Release --target trellis-cli -j $(JOBS)
	@rm -f tools/.trellis-*; touch $@

moss: $(MOSS_STAMP) ## The MOSS-SoundEffect env (MLX, Apple Silicon only)
$(MOSS_STAMP): requirements/moss-sfx.txt
	@[ -d tools/moss-soundeffect-mlx/.git ] || git clone --filter=blob:none $(MOSS_REPO) tools/moss-soundeffect-mlx
	git -C tools/moss-soundeffect-mlx fetch --quiet origin $(MOSS_COMMIT) || true
	git -C tools/moss-soundeffect-mlx checkout --quiet $(MOSS_COMMIT)
	uv venv --quiet --allow-existing --seed --python $(PYTHON_VERSION) tools/moss-soundeffect-mlx/.venv
	uv pip install --quiet --python tools/moss-soundeffect-mlx/.venv/bin/python -r requirements/moss-sfx.txt
	uv pip install --quiet --python tools/moss-soundeffect-mlx/.venv/bin/python --no-deps -e tools/moss-soundeffect-mlx
	@rm -f tools/.moss-*; touch $@

scoring: factory ## Optional: rank candidates by prompt match (torch, transformers) + `make models-scoring`
	uv pip install --quiet --python .venv/bin/python --require-hashes -r requirements/scoring.txt
matte: factory ## Optional: background removal (rembg, onnxruntime) + `make models-matte`
	uv pip install --quiet --python .venv/bin/python --require-hashes -r requirements/matte.txt
speech: tools/kokoro/.venv/.stamp ## Optional: text to speech env (Kokoro on MLX) + `make models-speech`
tools/kokoro/.venv/.stamp: requirements/speech.txt
	uv venv --quiet --allow-existing --python $(PYTHON_VERSION) tools/kokoro/.venv
	uv pip install --quiet --python tools/kokoro/.venv/bin/python --require-hashes -r requirements/speech.txt
	@touch $@
extras: scoring matte speech ## All optional envs (scoring, matte, speech)

explicit: factory ## Explicit tools: code and text in, assets out (Homebrew, Python, Node, .NET, SoundFont; no model weights)
	brew bundle --file=Brewfile --no-upgrade
	uv venv --quiet --allow-existing --python $(PYTHON_VERSION) tools/explicit/.venv
	UV_HTTP_TIMEOUT=180 uv pip install --quiet --python tools/explicit/.venv/bin/python --require-hashes -r requirements/explicit.txt
	mkdir -p tools/explicit/node && cp requirements/explicit-node/package.json requirements/explicit-node/package-lock.json tools/explicit/node/
	cd tools/explicit/node && PUPPETEER_CACHE_DIR="$$PWD/.cache/puppeteer" npm ci --ignore-scripts --no-audit --no-fund
	[ -x tools/explicit/dotnet/ysc ] || dotnet tool install YarnSpinner.Console --version 3.2.2 --tool-path tools/explicit/dotnet
	$(AEN) models download generaluser-gs
	$(AEN) tools check

comfyui: factory ## Optional: ComfyUI as an engine and a UI, sharing models/ (about 2 GB)
	@[ -d tools/ComfyUI/.git ] || git clone --filter=blob:none $(COMFY_REPO) tools/ComfyUI
	git -C tools/ComfyUI fetch --quiet origin $(COMFY_COMMIT) || true
	git -C tools/ComfyUI checkout --quiet $(COMFY_COMMIT)
	@[ -d tools/ComfyUI/custom_nodes/ComfyUI-GGUF/.git ] || git clone --filter=blob:none $(COMFY_GGUF_REPO) tools/ComfyUI/custom_nodes/ComfyUI-GGUF
	git -C tools/ComfyUI/custom_nodes/ComfyUI-GGUF fetch --quiet origin $(COMFY_GGUF_COMMIT) || true
	git -C tools/ComfyUI/custom_nodes/ComfyUI-GGUF checkout --quiet $(COMFY_GGUF_COMMIT)
	uv venv --quiet --allow-existing --python $(PYTHON_VERSION) tools/ComfyUI/.venv
	uv pip install --quiet --python tools/ComfyUI/.venv/bin/python -r tools/ComfyUI/requirements.txt -r tools/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt
	ln -sfn ../../../comfy_nodes/aeneas_nodes tools/ComfyUI/custom_nodes/aeneas_nodes
	.venv/bin/python scripts/comfyui_paths.py > tools/ComfyUI/extra_model_paths.yaml
comfyui-run: ## Start ComfyUI on 127.0.0.1:8188 (UI and engine for comfy_image)
	cd tools/ComfyUI && .venv/bin/python main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch

models: ## Download the models for GROUPS (default all four core models); add ACCEPT=dinov3 for 3D
	$(AEN) models download $(GROUPS) $(ACCEPT_FLAGS)
models-image: ## Image models only: Z-Image Turbo, FLUX.2 klein (15.7 GB)
	$(AEN) models download image
models-3d: ## TRELLIS.2 (16.5 GB); needs ACCEPT=dinov3 after reading the DINOv3 licence
	$(AEN) models download 3d $(ACCEPT_FLAGS)
models-sound: ## MOSS-SoundEffect (8.4 GB)
	$(AEN) models download sound
models-scoring: ## SigLIP and CLAP for ranking candidates (1.4 GB)
	$(AEN) models download scoring
models-upscale: ## Real-ESRGAN x4 (67 MB)
	$(AEN) models download upscale
models-matte: ## BiRefNet lite for background removal (224 MB)
	$(AEN) models download matte
models-speech: ## Kokoro 82M with six voices (330 MB)
	$(AEN) models download speech
models-extras: models-scoring models-upscale models-matte models-speech ## All optional models (2.1 GB)

check: ## Health check with a tiny job through every installed generator (about 8 minutes)
	$(AEN) check
check-quick: ## Health check without the generation jobs (seconds)
	$(AEN) check --quick
verify: ## Check the SHA-256 of every downloaded model file
	$(AEN) models verify --full
list: ## List the models and whether they are downloaded
	@$(AEN) models list
test: factory ## Run the test suite (no models or GPU needed)
	.venv/bin/python -m pytest -q tests

service-start: ## Start the factory service (the MCP server also starts it on demand)
	$(AEN) service start
service-stop: ## Stop the factory service
	$(AEN) service stop
autostart: factory ## Start the factory service at login (a macOS LaunchAgent); it stays small when idle
	$(AEN) service autostart on
autostart-off: ## Stop starting the service at login
	$(AEN) service autostart off
mcp-info: ## Show how to register the MCP server with Claude Code and Codex
	@echo "Claude Code:  claude mcp add --scope user aeneas -- $(CURDIR)/bin/aen mcp"
	@echo "Codex:        codex mcp add aeneas -- $(CURDIR)/bin/aen mcp"

# The editor extension (editors/vscode): VS Code, Cursor, Windsurf, VSCodium
VSCODE_CLI ?= $(shell command -v code 2>/dev/null || echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
vscode: ## Build the VS Code extension (editors/vscode/aeneas-factory.vsix); needs Node
	cd editors/vscode && npm ci --ignore-scripts --no-audit --no-fund && npm run package
vscode-install: vscode ## Build the extension and install it into VS Code (VSCODE_CLI=cursor for Cursor)
	"$(VSCODE_CLI)" --install-extension editors/vscode/aeneas-factory.vsix --force
vscode-test: ## Test the extension: unit tests, then integration tests in a real VS Code against the running service
	cd editors/vscode && npm ci --ignore-scripts --no-audit --no-fund && npm test

clean-tools: ## Remove the tool builds and envs (keeps sources and models)
	rm -rf tools/stable-diffusion.cpp/build tools/trellis.cpp/build tools/moss-soundeffect-mlx/.venv tools/kokoro/.venv tools/.sd-* tools/.trellis-* tools/.moss-*
distclean: ## Remove tools/ and .venv entirely (keeps models/)
	rm -rf tools .venv
