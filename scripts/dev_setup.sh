#!/usr/bin/env bash
# =============================================================================
# VoicePilot Developer Environment Setup
# Quick setup for contributors — assumes system packages are already installed
# (run ./scripts/install.sh first if not).
# =============================================================================

set -euo pipefail

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
error() { echo "[ERROR] $*" >&2; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

info "Setting up VoicePilot development environment…"

VENV_DIR="$PROJECT_ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
    if [[ -e "$VENV_DIR" ]]; then
        warn "$VENV_DIR exists but has no usable interpreter — recreating it"
        rm -rf "$VENV_DIR"
    fi
    python3 -m venv "$VENV_DIR"
    info "Virtual environment created"
fi

# A `uv venv` has no pip; without this, pip calls would leak to the system pip,
# which Ubuntu 24.04 / Mint 22 block as an externally-managed environment.
if ! "$VENV_PY" -m pip --version &>/dev/null; then
    info "Bootstrapping pip into the virtual environment…"
    "$VENV_PY" -m ensurepip --upgrade &>/dev/null \
        || { error "Could not bootstrap pip into $VENV_DIR"; exit 1; }
fi

# Install through the venv interpreter directly — no `activate` needed, and the
# right environment is guaranteed.
PIP=("$VENV_PY" -m pip)

"${PIP[@]}" install --upgrade pip wheel setuptools --quiet
"${PIP[@]}" install -r requirements-dev.txt --quiet
"${PIP[@]}" install -e ".[dev]" --quiet

# Pre-commit hooks — only meaningful inside a git repository.
if [[ -d .git ]]; then
    if "$VENV_PY" -m pre_commit --version &>/dev/null; then
        "$VENV_PY" -m pre_commit install
        info "Pre-commit hooks installed"
    else
        warn "pre-commit not available — skipping hook installation"
    fi
else
    warn "Not a git repository — skipping pre-commit hooks"
fi

mkdir -p tests/fixtures

info "Developer environment ready."
info "Run tests: $VENV_PY -m pytest"
info "Run app:   $VENV_DIR/bin/voicepilot --debug"
