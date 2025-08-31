#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a

DEFAULT_HOST="$REPO_ROOT/isaac-sim-host-5.0.0"
ISAAC_DIR="${ISAAC_DIR:-$DEFAULT_HOST}"
EXTS_USER="${EXTS_USER:-$ISAAC_DIR/extsUser}"

for bin in "$ISAAC_DIR/isaac-sim.xr.vr.sh" "$ISAAC_DIR/isaac-sim.xr.sh" "$ISAAC_DIR/isaac-sim.sh"; do
  if [[ -x "$bin" ]]; then LAUNCH_BIN="$bin"; break; fi
done
[[ -z "$LAUNCH_BIN" ]] && { echo "Could not find Isaac launch script under $ISAAC_DIR" >&2; exit 1; }

exec "$LAUNCH_BIN" \
  --ext-folder "$EXTS_USER" \
  --enable omni.agent.worldbuilder \
  --enable omni.agent.worldviewer \
  --enable omni.agent.worldsurveyor \
  --enable omni.agent.worldrecorder \
  --/exts/omni.agent.worldbuilder/auth_enabled=true \
  --/exts/omni.agent.worldviewer/auth_enabled=true \
  --/exts/omni.agent.worldsurveyor/auth_enabled=false \
  --/exts/omni.agent.worldrecorder/auth_enabled=true \
  "$@"
