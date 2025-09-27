#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTH_HEADER=( )
if [[ -f "$ROOT_DIR/.env" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ROOT_DIR/.env"; set +a
  if [[ -n "${AGENT_EXT_AUTH_TOKEN:-}" ]]; then
    AUTH_HEADER=(-H "Authorization: Bearer ${AGENT_EXT_AUTH_TOKEN}")
  fi
fi

services=(
  worldbuilder:8899
  worldviewer:8900
  worldsurveyor:8891
  worldrecorder:8892
  worldstreamer.rtmp:8906
  worldstreamer.srt:8908
)

fail=0
for svc in "${services[@]}"; do
  name="${svc%%:*}"; port="${svc##*:}"; url="http://localhost:${port}/health"
  echo "==> ${name} ${url}"
  out=$(curl -sS -m 5 "${AUTH_HEADER[@]}" "$url" || true)
  if echo "$out" | grep -q '"success"\s*:\s*true'; then
    echo "[ok] ${name}: healthy"
  else
    echo "[fail] ${name}: unhealthy or no response"; echo "$out"
    fail=1
  fi
done

exit $fail

