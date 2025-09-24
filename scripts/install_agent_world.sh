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

# Parse flags: --dest, --version, --uninstall
UNINSTALL_MODE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dest)
      DEST_DIR="$2"; shift 2;;
    -v|--version)
      DEFAULT_VERSION="$2"; shift 2;;
    -u|--uninstall)
      UNINSTALL_MODE=true; shift;;
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

precompile_extensions() {
  local src_base="$ROOT_DIR/agentworld-extensions"
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found; skipping bytecode precompile" >&2
    return
  fi
  echo "==> Precompiling extension modules"
  python3 -m compileall -q \
    "$src_base/omni.agent.worldbuilder" \
    "$src_base/omni.agent.worldviewer" \
    "$src_base/omni.agent.worldsurveyor" \
    "$src_base/omni.agent.worldrecorder" \
    "$src_base/omni.agent.worldstreamer.rtmp" \
    "$src_base/omni.agent.worldstreamer.srt"
}

link_extensions() {
  local exts_user="$1"
  echo "==> Linking extensions into: $exts_user"
  mkdir -p "$exts_user"
  local src_base="$ROOT_DIR/agentworld-extensions"
  local extensions=(
    omni.agent.worldbuilder
    omni.agent.worldviewer
    omni.agent.worldsurveyor
    omni.agent.worldrecorder
    omni.agent.worldstreamer.rtmp
    omni.agent.worldstreamer.srt
  )
  for d in "${extensions[@]}"; do
    if [[ -d "$src_base/$d" ]]; then
      local target="$exts_user/$d"
      [[ -e "$target" ]] && { echo "exists: $target (skip)"; continue; }
      ln -s "$src_base/$d" "$target"
      echo "linked: $target"
    fi
  done
  precompile_extensions
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
  --enable omni.agent.worldstreamer.srt \\
  --/exts/omni.agent.worldbuilder/auth_enabled=true \\
  --/exts/omni.agent.worldviewer/auth_enabled=true \\
  --/exts/omni.agent.worldsurveyor/auth_enabled=false \\
  --/exts/omni.agent.worldrecorder/auth_enabled=true \\
  --/exts/omni.agent.worldstreamer.srt/auth_enabled=true \\
  "\$@"
EOF
  chmod +x "$out_path"
}

create_env_symlinks() {
  echo "Creating .env symlinks for Docker Compose locations..."
  local env_file="$ROOT_DIR/.env"

  # Create symlinks for MCP servers and OME compose locations
  local mcp_link="$ROOT_DIR/docker/mcp-servers/.env"
  local ome_link="$ROOT_DIR/docker/ome/.env"

  # Remove existing files/links
  [[ -f "$mcp_link" || -L "$mcp_link" ]] && rm "$mcp_link"
  [[ -f "$ome_link" || -L "$ome_link" ]] && rm "$ome_link"

  # Create symlinks
  ln -s "../../.env" "$mcp_link" && echo "✓ Created $mcp_link -> .env"
  ln -s "../../.env" "$ome_link" && echo "✓ Created $ome_link -> .env"
}

create_mcp_venvs() {
  local mcp_dir="$ROOT_DIR/mcp-servers"
  local venv_path="$mcp_dir/venv"
  
  echo "==> Setting up unified MCP server virtual environment..."
  
  # Create single virtual environment for all MCP servers
  python3 -m venv "$venv_path"
  
  # Upgrade pip and install build tools
  "$venv_path/bin/pip" install --upgrade pip setuptools wheel
  
  # Install unified package with all dependencies
  cd "$mcp_dir"
  "$venv_path/bin/pip" install -e .
  
  echo "✓ Unified MCP venv created successfully at $venv_path"
  echo "==> MCP virtual environment setup complete!"
}

cleanup_mcp_venvs() {
  local mcp_dir="$ROOT_DIR/mcp-servers"
  local venv_path="$mcp_dir/venv"
  
  echo "==> Removing unified MCP server virtual environment..."
  
  if [[ -d "$venv_path" ]]; then
    echo "Removing unified MCP venv..."
    rm -rf "$venv_path"
    echo "✓ Unified MCP venv removed"
  fi
  
  # Also clean up any old individual venvs
  for server_dir in "$mcp_dir"/*; do
    if [[ -d "$server_dir" ]]; then
      local old_venv_path="$server_dir/venv"
      if [[ -d "$old_venv_path" ]]; then
        echo "Removing old individual venv at $old_venv_path..."
        rm -rf "$old_venv_path"
      fi
    fi
  done
  
  echo "==> MCP virtual environment cleanup complete!"
}

cleanup_extension_symlinks() {
  local exts_user="$1"
  echo "==> Removing Agent World extension symlinks from $exts_user..."
  
  local extensions=("omni.agent.worldbuilder" "omni.agent.worldviewer" "omni.agent.worldsurveyor" "omni.agent.worldrecorder" "omni.agent.worldstreamer.rtmp" "omni.agent.worldstreamer.srt")
  for ext in "${extensions[@]}"; do
    local link_path="$exts_user/$ext"
    if [[ -L "$link_path" ]]; then
      echo "Removing symlink: $link_path"
      rm "$link_path"
      echo "✓ $ext symlink removed"
    elif [[ -e "$link_path" ]]; then
      echo "⚠️  $link_path exists but is not a symlink (skipping)"
    fi
  done
  
  echo "==> Extension symlinks cleanup complete!"
}

cleanup_generated_files() {
  echo "==> Removing generated files..."
  
  # Remove .env file and symlinks
  local env_path="$ROOT_DIR/.env"
  local mcp_link="$ROOT_DIR/docker/mcp-servers/.env"
  local ome_link="$ROOT_DIR/docker/ome/.env"

  [[ -f "$mcp_link" || -L "$mcp_link" ]] && rm "$mcp_link" && echo "✓ Removed $mcp_link"
  [[ -f "$ome_link" || -L "$ome_link" ]] && rm "$ome_link" && echo "✓ Removed $ome_link"

  if [[ -f "$env_path" ]]; then
    echo "Removing environment file: $env_path"
    rm "$env_path"
    echo "✓ .env file removed"
  fi
  
  # Remove launch script
  local launcher="$ROOT_DIR/scripts/launch_agent_world.sh"
  if [[ -f "$launcher" ]]; then
    echo "Removing launch script: $launcher"
    rm "$launcher"
    echo "✓ launch script removed"
  fi
  
  echo "==> Generated files cleanup complete!"
}

is_local_isaac_installation() {
  local isaac_dir="$1"
  # Check if it's under our repo root (local installation)
  [[ "$isaac_dir" == "$ROOT_DIR"/* ]]
}

uninstall() {
  echo "==> Agent World Uninstaller (Linux/macOS)"
  echo "This will remove Agent World components."
  
  if ! prompt_yn "Are you sure you want to uninstall Agent World?" n; then
    echo "Uninstall cancelled."
    exit 0
  fi
  
  # Clean up MCP virtual environments
  cleanup_mcp_venvs
  
  # Clean up generated files (.env, launch script, etc.)
  cleanup_generated_files
  
  # Handle extension symlinks
  echo ""
  echo "Extension symlink cleanup:"
  read -r -p "Enter the extsUser path where extensions were linked (leave blank to skip): " exts_user || true
  
  if [[ -n "$exts_user" && -d "$exts_user" ]]; then
    cleanup_extension_symlinks "$exts_user"
  elif [[ -n "$exts_user" ]]; then
    echo "Directory not found: $exts_user (skipping extension cleanup)"
  else
    echo "Skipping extension symlink cleanup"
  fi
  
  # Handle Isaac Sim installation
  echo ""
  echo "Isaac Sim installation cleanup:"
  read -r -p "Enter the Isaac Sim installation path (leave blank to skip): " isaac_dir || true
  
  if [[ -n "$isaac_dir" && -d "$isaac_dir" ]]; then
    if is_local_isaac_installation "$isaac_dir"; then
      if prompt_yn "Remove local Isaac Sim installation at $isaac_dir?" n; then
        echo "Removing Isaac Sim installation: $isaac_dir"
        rm -rf "$isaac_dir"
        echo "✓ Isaac Sim installation removed"
      fi
    else
      echo "ℹ️  Isaac Sim installation is external ($isaac_dir)"
      echo "   You may need to manually remove Agent World extension symlinks if any were created."
      echo "   Extension symlinks would be in: $isaac_dir/extsUser/"
    fi
  else
    echo "Skipping Isaac Sim cleanup"
  fi
  
  echo ""
  echo "==> Uninstall complete!"
  echo "Note: This script does not remove:"
  echo "  - The Agent World repository itself"
  echo "  - External Isaac Sim installations"
  echo "  - Manual modifications you may have made"
}

main() {
  if [[ "$UNINSTALL_MODE" == "true" ]]; then
    uninstall
    return 0
  fi
  
  echo "==> Agent World Installer (Linux/macOS)"
  local have_isaac; prompt_yn "Is Isaac Sim already installed locally?" y && have_isaac=1 || have_isaac=0
  local isaac_dir
  if [[ "$have_isaac" -eq 1 ]]; then
    local default="isaac-sim-host-${DEFAULT_VERSION}"
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
    local token secret ome_token; token=$(generate_hex 32); secret=$(generate_hex 48); ome_token=$(generate_hex 16)
    cat > "$env_path" <<ENV
# Agent World environment
AGENT_EXT_AUTH_ENABLED=1
AGENT_EXT_AUTH_TOKEN=$token
AGENT_EXT_HMAC_SECRET=$secret
# Bearer auth (disabled by default, HMAC preferred)
AGENT_EXT_BEARER_AUTH_ENABLED=0
# Optional per-service overrides
# AGENT_WORLDBUILDER_AUTH_TOKEN=$token
# AGENT_WORLDBUILDER_HMAC_SECRET=$secret
# AGENT_WORLDBUILDER_BEARER_AUTH_ENABLED=1
# AGENT_WORLDVIEWER_AUTH_TOKEN=$token
# AGENT_WORLDVIEWER_HMAC_SECRET=$secret
# AGENT_WORLDSURVEYOR_AUTH_TOKEN=$token
# AGENT_WORLDSURVEYOR_HMAC_SECRET=$secret
# AGENT_WORLDRECORDER_AUTH_TOKEN=$token
# AGENT_WORLDRECORDER_HMAC_SECRET=$secret

# OME (OvenMediaEngine) Configuration
OME_IMAGE=airensoft/ovenmediaengine:latest
OME_NAME=ome
OME_API_TOKEN=$ome_token
ENV
    echo "Wrote secrets to: $env_path"
    create_env_symlinks
  fi

  if prompt_yn "Create Python virtual environment for MCP servers?" y; then
    create_mcp_venvs
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
