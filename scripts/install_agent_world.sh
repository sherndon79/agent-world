#!/usr/bin/env bash
set -euo pipefail

# Agent World installer helper (Linux/macOS)
# - Detect or install Isaac Sim host bundle
# - Symlink extensions into extsUser
# - Generate auth secrets into .env (optional)
# - Create a launcher wrapper

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_VERSION="5.0.0"
DEST_DIR=""

# Parse flags: --dest, --version
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dest)
      DEST_DIR="$2"; shift 2;;
    -v|--version)
      DEFAULT_VERSION="$2"; shift 2;;
    --) shift; break;;
    *) break;;
  esac
done

prompt_yn() {
  local prompt="$1"; shift
  local def="${1:-}"; shift || true
  local suffix="[y/N]"; [[ "$def" =~ ^([Yy])$ ]] && suffix="[Y/n]"
  local ans
  while true; do
    read -r -p "$prompt $suffix " ans || true
    ans=${ans:-$def}
    case "${ans,,}" in
      y|yes) return 0;;
      n|no) return 1;;
      *) echo "Please answer yes or no.";;
    esac
  done
}

require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }

generate_hex() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  elif command -v python3 >/dev/null 2>&1; then
    python3 - <<PY
import secrets
print(secrets.token_hex(${bytes}))
PY
  else
    hexdump -vn "$bytes" -e ' /1 "%02x"' /dev/urandom 2>/dev/null || date +%s%N
  fi
}

install_from_zip() {
  local version="$1" url="$2" out_dir="$3"
  require_cmd wget; require_cmd unzip
  mkdir -p "$out_dir"
  local zip_name="isaac-sim-host-${version}.zip"
  echo "==> Downloading Isaac Sim ($version)"
  wget -O "$zip_name" "$url"
  echo "==> Unpacking to: $out_dir"
  unzip -q "$zip_name" -d "$out_dir"
  rm -f "$zip_name"
}

detect_local_zip() {
  local z
  z=$(ls -1 isaac-sim-standalone-*-linux-x86_64.zip 2>/dev/null | head -n1 || true)
  if [[ -n "$z" ]]; then echo "$z"; return 0; fi
  z=$(ls -1 isaac-sim-standalone-*.zip 2>/dev/null | head -n1 || true)
  [[ -n "$z" ]] && echo "$z"
}

link_extensions() {
  local exts_user="$1"
  echo "==> Linking extensions into: $exts_user"
  mkdir -p "$exts_user"
  local src_base="$ROOT_DIR/agentworld-extensions"
  for d in omni.agent.worldbuilder omni.agent.worldviewer omni.agent.worldsurveyor omni.agent.worldrecorder; do
    if [[ -d "$src_base/$d" ]]; then
      local target="$exts_user/$d"
      [[ -e "$target" ]] && { echo "exists: $target (skip)"; continue; }
      ln -s "$src_base/$d" "$target"
      echo "linked: $target"
    fi
  done
}

create_launcher() {
  local isaac_dir="$1" exts_user="$2" out_path="$3"
  cat > "$out_path" <<EOF
#!/usr/bin/env bash
set -e

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="\$(cd "\$SCRIPT_DIR/.." && pwd)"
ENV_FILE="\$REPO_ROOT/.env"
[[ -f "\$ENV_FILE" ]] && set -a && source "\$ENV_FILE" && set +a

ISAAC_DIR="$isaac_dir"
EXTS_USER="$exts_user"

for bin in "\$ISAAC_DIR/isaac-sim.xr.vr.sh" "\$ISAAC_DIR/isaac-sim.xr.sh" "\$ISAAC_DIR/isaac-sim.sh"; do
  if [[ -x "\$bin" ]]; then LAUNCH_BIN="\$bin"; break; fi
done
[[ -z "\$LAUNCH_BIN" ]] && { echo "Could not find Isaac launch script in \$ISAAC_DIR" >&2; exit 1; }

exec "\$LAUNCH_BIN" \\
  --ext-folder "\$EXTS_USER" \\
  --enable omni.agent.worldbuilder \\
  --enable omni.agent.worldviewer \\
  --enable omni.agent.worldsurveyor \\
  --enable omni.agent.worldrecorder \\
  --/exts/omni.agent.worldbuilder/auth_enabled=true \\
  --/exts/omni.agent.worldviewer/auth_enabled=true \\
  --/exts/omni.agent.worldsurveyor/auth_enabled=false \\
  --/exts/omni.agent.worldrecorder/auth_enabled=true \\
  "\$@"
EOF
  chmod +x "$out_path"
}

main() {
  echo "==> Agent World Installer (Linux/macOS)"
  local have_isaac; prompt_yn "Is Isaac Sim already installed locally?" y && have_isaac=1 || have_isaac=0
  local isaac_dir
  if [[ "$have_isaac" -eq 1 ]]; then
    local default="${HOME}/agent-world-prod/isaac-sim-host-${DEFAULT_VERSION}"
    read -r -p "Enter Isaac Sim host path [$default]: " isaac_dir || true
    isaac_dir=${isaac_dir:-$default}
    [[ -d "$isaac_dir" ]] || { echo "Not found: $isaac_dir" >&2; exit 1; }
  else
    read -r -p "Enter version to install [${DEFAULT_VERSION}]: " version || true
    version=${version:-$DEFAULT_VERSION}
    read -r -p "Enter download URL for Isaac Sim host zip (leave blank to use local zip): " url || true
    if [[ -z "${url:-}" ]]; then
      local_zip=$(detect_local_zip || true)
      if [[ -n "$local_zip" ]]; then
        isaac_dir="${DEST_DIR:-$PWD/isaac-sim-host-${version}}"
        mkdir -p "$isaac_dir"
        echo "==> Using local zip: $local_zip"
        echo "==> Unpacking to: $isaac_dir"
        unzip -q "$local_zip" -d "$isaac_dir"
      else
        echo "No local zip found. Please provide a download URL." >&2
        exit 1
      fi
    else
      isaac_dir="${DEST_DIR:-$PWD/isaac-sim-host-${version}}"
      install_from_zip "$version" "$url" "$isaac_dir"
    fi
  fi

  if prompt_yn "Enable API authentication and generate secrets now?" y; then
    local env_path="$ROOT_DIR/.env"
    local token secret; token=$(generate_hex 32); secret=$(generate_hex 48)
    cat > "$env_path" <<ENV
# Agent World environment
AGENT_EXT_AUTH_ENABLED=1
AGENT_EXT_AUTH_TOKEN=$token
AGENT_EXT_HMAC_SECRET=$secret
# Optional per-service overrides
# AGENT_WORLDBUILDER_AUTH_TOKEN=$token
# AGENT_WORLDBUILDER_HMAC_SECRET=$secret
# AGENT_WORLDVIEWER_AUTH_TOKEN=$token
# AGENT_WORLDVIEWER_HMAC_SECRET=$secret
# AGENT_WORLDSURVEYOR_AUTH_TOKEN=$token
# AGENT_WORLDSURVEYOR_HMAC_SECRET=$secret
# AGENT_WORLDRECORDER_AUTH_TOKEN=$token
# AGENT_WORLDRECORDER_HMAC_SECRET=$secret
ENV
    echo "Wrote secrets to: $env_path"
  fi

  local default_exts="$isaac_dir/extsUser"
  read -r -p "Enter extsUser path for extensions [$default_exts]: " exts_user || true
  exts_user=${exts_user:-$default_exts}
  if prompt_yn "Create symlinks for extensions into '$exts_user'?" y; then
    link_extensions "$exts_user"
  fi

  if prompt_yn "Create an Isaac Sim launcher script?" y; then
    local default_launcher="$ROOT_DIR/scripts/launch_agent_world.sh"
    mkdir -p "$ROOT_DIR/scripts"
    create_launcher "$isaac_dir" "$exts_user" "$default_launcher"
    echo "Launcher created: $default_launcher"
  fi

  echo "==> Done. You can run scripts/launch_agent_world.sh to start Isaac Sim."
}

main "$@"
