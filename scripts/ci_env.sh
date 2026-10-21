#!/bin/sh
# CI on the self-hosted runner: make sure uv is available without touching the machine (a pinned copy in
# the job's own folder when the runner has none). Usage in a workflow step:  . scripts/ci_env.sh
UV_VERSION=0.11.28
if ! command -v uv >/dev/null 2>&1; then
  if [ ! -x .ci/uv/bin/uv ]; then
    python3 -m venv .ci/uv && .ci/uv/bin/pip install --quiet "uv==$UV_VERSION"
  fi
  PATH="$PWD/.ci/uv/bin:$PATH"; export PATH
  [ -n "$GITHUB_PATH" ] && echo "$PWD/.ci/uv/bin" >> "$GITHUB_PATH"
fi
uv --version
