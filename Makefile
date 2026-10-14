# Aeneas Factory: build the tools, download the models, check that everything works.
# `make help` lists the targets. Everything lands inside this folder (tools/, models/).

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Pinned upstream sources: the exact commits this repository was tested with.
SD_REPO        := https://github.com/leejet/stable-diffusion.cpp
SD_COMMIT      := 59c23bce0d82be3a922023ab811194f05b3e2faa
TRELLIS_REPO   := https://github.com/pwilkin/trellis.cpp
TRELLIS_COMMIT := 2516c48b677050c570f47eba2e68dc8a5bc918b0
MOSS_REPO      := https://github.com/xocialize/moss-soundeffect-mlx.git
MOSS_COMMIT    := 4e8e3e36d4d9c991d16a3e65a4b7099d406b9ed8
MOSS_PYTHON    ?= 3.12

JOBS        ?= $(shell sysctl -n hw.ncpu 2>/dev/null || nproc)
CMAKE_ARGS  ?=
SD_CLI      := tools/stable-diffusion.cpp/build/bin/sd-cli
TRELLIS_CLI := tools/trellis.cpp/build/trellis-cli
MOSS_PY     := tools/moss-soundeffect-mlx/.venv/bin/python

.PHONY: help all install prereqs tools sd trellis moss models models-image models-3d models-sound \
        check check-quick verify list clean-tools distclean

help: ## Show this list
	@echo "Aeneas Factory: local images, 3D models and sound effects on Apple Silicon."
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'
	@echo
	@echo "Start with: make install   (about 1 GB of tools, 40 GB of models; see README.md)"

install: prereqs tools models check ## Everything: check prerequisites, build tools, download all models, run the check
all: install

prereqs: ## Check that the build prerequisites are installed
	@ok=1; \
	[ "$$(uname -s)/$$(uname -m)" = "Darwin/arm64" ] || { echo "WARN  not macOS on Apple Silicon: sd-cli and trellis-cli need CMAKE_ARGS for your GPU, and ai-sfx (MLX) will not run"; }; \
	xcode-select -p >/dev/null 2>&1 || { echo "MISS  Xcode Command Line Tools: xcode-select --install"; ok=0; }; \
	for c in git cmake curl uv; do command -v $$c >/dev/null || { echo "MISS  $$c: brew install $$c"; ok=0; }; done; \
	command -v python3 >/dev/null || { echo "MISS  python3"; ok=0; }; \
	free=$$(df -k . | awk 'NR==2 {print int($$4/1048576)}'); \
	[ $$free -ge 45 ] || echo "WARN  $$free GB free here; all models and tools need about 45 GB"; \
	[ $$ok = 1 ] && echo "prerequisites ok ($$free GB free)" || { echo "install the missing tools above, then run make again"; exit 1; }

tools: sd trellis moss ## Build all three tools (stable-diffusion.cpp, trellis.cpp, MOSS env)

sd: $(SD_CLI) ## Build stable-diffusion.cpp (sd-cli, Metal)
$(SD_CLI):
	@[ -d tools/stable-diffusion.cpp/.git ] || git clone --filter=blob:none $(SD_REPO) tools/stable-diffusion.cpp
	git -C tools/stable-diffusion.cpp fetch --quiet origin $(SD_COMMIT) || true
	git -C tools/stable-diffusion.cpp checkout --quiet $(SD_COMMIT)
	git -C tools/stable-diffusion.cpp submodule update --init --recursive --quiet
	cmake -S tools/stable-diffusion.cpp -B tools/stable-diffusion.cpp/build -DCMAKE_BUILD_TYPE=Release -DSD_METAL=ON $(CMAKE_ARGS)
	cmake --build tools/stable-diffusion.cpp/build --config Release --target sd-cli -j $(JOBS)

trellis: $(TRELLIS_CLI) ## Build trellis.cpp (trellis-cli, Metal)
$(TRELLIS_CLI):
	@[ -d tools/trellis.cpp/.git ] || git clone --filter=blob:none $(TRELLIS_REPO) tools/trellis.cpp
	git -C tools/trellis.cpp fetch --quiet origin $(TRELLIS_COMMIT) || true
	git -C tools/trellis.cpp checkout --quiet $(TRELLIS_COMMIT)
	git -C tools/trellis.cpp submodule update --init --recursive --quiet
	cmake -S tools/trellis.cpp -B tools/trellis.cpp/build -DCMAKE_BUILD_TYPE=Release $(CMAKE_ARGS)
	cmake --build tools/trellis.cpp/build --config Release --target trellis-cli -j $(JOBS)

moss: $(MOSS_PY) ## Set up the MOSS-SoundEffect Python env (MLX, Apple Silicon only)
$(MOSS_PY): requirements/moss-sfx.txt
	@[ -d tools/moss-soundeffect-mlx/.git ] || git clone --filter=blob:none $(MOSS_REPO) tools/moss-soundeffect-mlx
	git -C tools/moss-soundeffect-mlx fetch --quiet origin $(MOSS_COMMIT) || true
	git -C tools/moss-soundeffect-mlx checkout --quiet $(MOSS_COMMIT)
	uv venv --quiet --allow-existing --seed --python $(MOSS_PYTHON) tools/moss-soundeffect-mlx/.venv
	uv pip install --quiet --python $(MOSS_PY) -r requirements/moss-sfx.txt
	uv pip install --quiet --python $(MOSS_PY) --no-deps -e tools/moss-soundeffect-mlx
	@touch $(MOSS_PY)

models: ## Download every model (about 40 GB; resumes, checks SHA-256)
	bin/ai-models download all
models-image: ## Download the image models only (Z-Image Turbo, FLUX.2 klein: 15.7 GB)
	bin/ai-models download image
models-3d: ## Download TRELLIS.2 only (16.5 GB)
	bin/ai-models download 3d
models-sound: ## Download MOSS-SoundEffect only (8.4 GB)
	bin/ai-models download sound

check: ## Health check with a tiny job through every installed generator (about 7 minutes)
	bin/ai-check
check-quick: ## Health check without the generation jobs (seconds)
	bin/ai-check --quick
verify: ## Check the SHA-256 of every downloaded model file
	bin/ai-models verify --full
list: ## List the models and whether they are downloaded
	@bin/ai-models list

clean-tools: ## Remove the tool builds (keeps the sources and the models)
	rm -rf tools/stable-diffusion.cpp/build tools/trellis.cpp/build tools/moss-soundeffect-mlx/.venv
distclean: ## Remove tools/ entirely (keeps models/)
	rm -rf tools
