#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISAAC_DIR="${ISAAC_DIR:-$ROOT_DIR/isaac-sim-host-5.0.0}"
PYTHON_SH="$ISAAC_DIR/python.sh"

if [[ ! -x "$PYTHON_SH" ]]; then
  echo "Isaac Sim python.sh not found at $PYTHON_SH" >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/agentworld-extensions:$PYTHONPATH"

if ! "$PYTHON_SH" -m pip show pytest >/dev/null 2>&1; then
  echo "==> Installing pytest into Isaac Sim Python"
  "$PYTHON_SH" -m pip install --upgrade pip >/dev/null
  "$PYTHON_SH" -m pip install pytest >/dev/null
fi

"$PYTHON_SH" -m pytest "$ROOT_DIR/agentworld-extensions/tests/worldbuilder" "$@"
