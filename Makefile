# Aeneas Factory: `make <step>` runs `python3 install.py <step>` (the installer works on macOS, Linux and
# Windows; on Windows run `py install.py <step>`). `make help` lists the steps.
#   make install GROUPS=image          images only
#   make install ACCEPT=dinov3         everything, after reading the DINOv3 licence
#   make sd AEN_GPU=vulkan             choose the GPU backend (metal, cuda, vulkan, cpu)
# Variables passed through: GROUPS ACCEPT AEN_GPU CMAKE_ARGS JOBS PYTHON_VERSION VSCODE_CLI

PYTHON ?= $(shell command -v python3 || command -v python)
export GROUPS ACCEPT AEN_GPU CMAKE_ARGS JOBS PYTHON_VERSION VSCODE_CLI
.DEFAULT_GOAL := help

all: install

%: FORCE
	@$(PYTHON) install.py $@

FORCE: ;
Makefile: ;
.PHONY: all FORCE
