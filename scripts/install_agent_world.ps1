Param(
  [Alias('Dest')]
  [string]$IsaacDir,
  [string]$Version = "5.0.0",
  [string]$ZipUrl,
  [Alias('u')]
  [switch]$Uninstall
)

function Read-Choice($Prompt, $Default=$true) {
  $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
  while ($true) {
    $ans = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $Default }
    switch ($ans.ToLower()) {
      "y" { return $true }
      "yes" { return $true }
      "n" { return $false }
      "no" { return $false }
      default { Write-Host "Please answer yes or no." }
    }
  }
}

function New-Hex($bytes=32) {
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $buf = New-Object byte[] $bytes
  $rng.GetBytes($buf)
  ($buf | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Remove-McpVenvs {
  Write-Host "==> Removing unified MCP server virtual environment..." -ForegroundColor Yellow
  $mcpDir = Join-Path (Split-Path $PSScriptRoot -Parent) "mcp-servers"
  $venvPath = Join-Path $mcpDir "venv"
  
  if (Test-Path $venvPath) {
    Write-Host "Removing unified MCP venv..."
    Remove-Item -Path $venvPath -Recurse -Force
    Write-Host "✓ Unified MCP venv removed" -ForegroundColor Green
  }
  
  # Also clean up any old individual venvs
  Get-ChildItem -Path $mcpDir -Directory | ForEach-Object {
    $oldVenvPath = Join-Path $_.FullName "venv"
    if (Test-Path $oldVenvPath) {
      Write-Host "Removing old individual venv at $oldVenvPath..."
      Remove-Item -Path $oldVenvPath -Recurse -Force
    }
  }
  
  Write-Host "==> MCP virtual environment cleanup complete!" -ForegroundColor Green
}

function Remove-ExtensionSymlinks {
  param([string]$ExtsUser)
  Write-Host "==> Removing Agent World extension symlinks from $ExtsUser..." -ForegroundColor Yellow
  
  $extensions = @(
    "omni.agent.worldbuilder",
    "omni.agent.worldviewer",
    "omni.agent.worldsurveyor",
    "omni.agent.worldrecorder",
    "omni.agent.worldstreamer.rtmp",
    "omni.agent.worldstreamer.srt"
  )
  foreach ($ext in $extensions) {
    $linkPath = Join-Path $ExtsUser $ext
    if (Test-Path $linkPath) {
      $item = Get-Item $linkPath
      if ($item.LinkType -eq "Junction") {
        Write-Host "Removing junction: $linkPath"
        Remove-Item -Path $linkPath -Force
        Write-Host "✓ $ext junction removed" -ForegroundColor Green
      } else {
        Write-Host "⚠️  $linkPath exists but is not a junction (skipping)" -ForegroundColor Yellow
      }
    }
  }
  
  Write-Host "==> Extension symlinks cleanup complete!" -ForegroundColor Green
}

function Invoke-PrecompileExtensions {
  $repoRoot = Split-Path $PSScriptRoot -Parent
  $srcBase = Join-Path $repoRoot "agentworld-extensions"
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Warning "python executable not found; skipping bytecode precompile"
    return
  }
  Write-Host "==> Precompiling extension modules"
  python -m compileall -q \
    (Join-Path $srcBase 'omni.agent.worldbuilder') \
    (Join-Path $srcBase 'omni.agent.worldviewer') \
    (Join-Path $srcBase 'omni.agent.worldsurveyor') \
    (Join-Path $srcBase 'omni.agent.worldrecorder') \
    (Join-Path $srcBase 'omni.agent.worldstreamer.rtmp') \
    (Join-Path $srcBase 'omni.agent.worldstreamer.srt')
}

function Remove-GeneratedFiles {
  Write-Host "==> Removing generated files..." -ForegroundColor Yellow
  $repoRoot = Split-Path $PSScriptRoot -Parent
  
  # Remove .env file
  $envPath = Join-Path $repoRoot ".env"
  if (Test-Path $envPath) {
    Write-Host "Removing environment file: $envPath"
    Remove-Item -Path $envPath -Force
    Write-Host "✓ .env file removed" -ForegroundColor Green
  }
  
  # Remove launch script
  $launcher = Join-Path $repoRoot "scripts/launch_agent_world.ps1"
  if (Test-Path $launcher) {
    Write-Host "Removing launch script: $launcher"
    Remove-Item -Path $launcher -Force
    Write-Host "✓ launch script removed" -ForegroundColor Green
  }
  
  Write-Host "==> Generated files cleanup complete!" -ForegroundColor Green
}

function Test-LocalIsaacInstallation {
  param([string]$IsaacDir)
  $repoRoot = Split-Path $PSScriptRoot -Parent
  return $IsaacDir.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

function Invoke-Uninstall {
  Write-Host "==> Agent World Uninstaller (Windows)" -ForegroundColor Cyan
  Write-Host "This will remove Agent World components." -ForegroundColor Yellow
  
  if (-not (Read-Choice "Are you sure you want to uninstall Agent World?" $false)) {
    Write-Host "Uninstall cancelled." -ForegroundColor Yellow
    exit 0
  }
  
  # Clean up MCP virtual environments
  Remove-McpVenvs
  
  # Clean up generated files (.env, launch script, etc.)
  Remove-GeneratedFiles
  
  # Handle extension symlinks
  Write-Host ""
  Write-Host "Extension symlink cleanup:" -ForegroundColor Cyan
  $extsUser = Read-Host "Enter the extsUser path where extensions were linked (leave blank to skip)"
  
  if ($extsUser -and (Test-Path $extsUser)) {
    Remove-ExtensionSymlinks $extsUser
  } elseif ($extsUser) {
    Write-Host "Directory not found: $extsUser (skipping extension cleanup)" -ForegroundColor Yellow
  } else {
    Write-Host "Skipping extension symlink cleanup" -ForegroundColor Yellow
  }
  
  # Handle Isaac Sim installation
  Write-Host ""
  Write-Host "Isaac Sim installation cleanup:" -ForegroundColor Cyan
  $isaacDir = Read-Host "Enter the Isaac Sim installation path (leave blank to skip)"
  
  if ($isaacDir -and (Test-Path $isaacDir)) {
    if (Test-LocalIsaacInstallation $isaacDir) {
      if (Read-Choice "Remove local Isaac Sim installation at $isaacDir?" $false) {
        Write-Host "Removing Isaac Sim installation: $isaacDir"
        Remove-Item -Path $isaacDir -Recurse -Force
        Write-Host "✓ Isaac Sim installation removed" -ForegroundColor Green
      }
    } else {
      Write-Host "ℹ️  Isaac Sim installation is external ($isaacDir)" -ForegroundColor Cyan
      Write-Host "   You may need to manually remove Agent World extension junctions if any were created." -ForegroundColor Yellow
      Write-Host "   Extension junctions would be in: $isaacDir/extsUser/" -ForegroundColor Yellow
    }
  } else {
    Write-Host "Skipping Isaac Sim cleanup" -ForegroundColor Yellow
  }
  
  Write-Host ""
  Write-Host "==> Uninstall complete!" -ForegroundColor Green
  Write-Host "Note: This script does not remove:" -ForegroundColor Yellow
  Write-Host "  - The Agent World repository itself"
  Write-Host "  - External Isaac Sim installations"
  Write-Host "  - Manual modifications you may have made"
}

# Check for uninstall mode
if ($Uninstall) {
  Invoke-Uninstall
  exit 0
}

Write-Host "==> Agent World Installer (Windows)" -ForegroundColor Cyan

if (-not $IsaacDir) {
  $hasIsaac = Read-Choice "Is Isaac Sim already installed locally?" $true
  if ($hasIsaac) {
    $default = "isaac-sim-host-$Version"
    $IsaacDir = Read-Host "Enter Isaac Sim host path [$default]"
    if (-not $IsaacDir) { $IsaacDir = $default }
  } else {
    # Allow using a local zip if present
    if (-not $ZipUrl) {
      $localZip = Get-ChildItem -Path (Get-Location) -Filter "isaac-sim-standalone-*-windows-x86_64.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $IsaacDir) {
      $IsaacDir = Join-Path (Get-Location) "isaac-sim-host-$Version"
    }
    if ($localZip) {
      Write-Host "==> Using local zip: $($localZip.Name)"
      Write-Host "==> Unpacking to: $IsaacDir"
      Expand-Archive -Path $localZip.FullName -DestinationPath $IsaacDir -Force
    } else {
      if (-not $ZipUrl) {
        $ZipUrl = "https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-$Version-windows-x86_64.zip"
      }
      $outZip = "isaac-sim-host-$Version.zip"
      Write-Host "==> Downloading Isaac Sim host: $ZipUrl"
      Invoke-WebRequest -Uri $ZipUrl -OutFile $outZip
      Write-Host "==> Unpacking to: $IsaacDir"
      Expand-Archive -Path $outZip -DestinationPath $IsaacDir -Force
      Remove-Item $outZip -Force
    }
  }
}

if (-not (Test-Path $IsaacDir)) { throw "Isaac dir not found: $IsaacDir" }

# Auth secrets
if (Read-Choice "Enable API authentication and generate secrets now?" $true) {
  $envPath = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
  $token = New-Hex 32
  $secret = New-Hex 48
  Set-Content -LiteralPath $envPath -Value @(
    "# Agent World environment",
    "AGENT_EXT_AUTH_ENABLED=1",
    "AGENT_EXT_AUTH_TOKEN=$token",
    "AGENT_EXT_HMAC_SECRET=$secret",
    "# Bearer auth (disabled by default, HMAC preferred)",
    "AGENT_EXT_BEARER_AUTH_ENABLED=0",
    "# Optional per-service overrides",
    "# AGENT_WORLDBUILDER_AUTH_TOKEN=$token",
    "# AGENT_WORLDBUILDER_HMAC_SECRET=$secret",
    "# AGENT_WORLDBUILDER_BEARER_AUTH_ENABLED=1",
    "# AGENT_WORLDVIEWER_AUTH_TOKEN=$token",
    "# AGENT_WORLDVIEWER_HMAC_SECRET=$secret",
    "# AGENT_WORLDSURVEYOR_AUTH_TOKEN=$token",
    "# AGENT_WORLDSURVEYOR_HMAC_SECRET=$secret",
    "# AGENT_WORLDRECORDER_AUTH_TOKEN=$token",
    "# AGENT_WORLDRECORDER_HMAC_SECRET=$secret"
  ) -NoNewline:$false
  Write-Host "Wrote secrets to: $envPath"
}

# Create unified MCP virtual environment
if (Read-Choice "Create Python virtual environment for MCP servers?" $true) {
  Write-Host "==> Setting up unified MCP server virtual environment..."
  $mcpDir = Join-Path (Split-Path $PSScriptRoot -Parent) "mcp-servers"
  $venvPath = Join-Path $mcpDir "venv"
  
  # Create single virtual environment for all MCP servers
  python -m venv $venvPath
  
  # Upgrade pip and install build tools
  & "$venvPath\Scripts\pip.exe" install --upgrade pip setuptools wheel
  
  # Install unified package with all dependencies
  Push-Location $mcpDir
  & "$venvPath\Scripts\pip.exe" install -e .
  Pop-Location
  
  Write-Host "✓ Unified MCP venv created successfully at $venvPath" -ForegroundColor Green
  Write-Host "==> MCP virtual environment setup complete!"
}

# Link extensions into extsUser via Junctions
$defaultExts = Join-Path $IsaacDir "extsUser"
$extsUser = Read-Host "Enter extsUser path for extensions [$defaultExts]"
if (-not $extsUser) { $extsUser = $defaultExts }
if (-not (Test-Path $extsUser)) { New-Item -ItemType Directory -Path $extsUser | Out-Null }

if (Read-Choice "Create links for Agent World extensions into '$extsUser'?" $true) {
  $repoRoot = Split-Path $PSScriptRoot -Parent
  $srcBase = Join-Path $repoRoot "agentworld-extensions"
  $exts = @(
    'omni.agent.worldbuilder',
    'omni.agent.worldviewer',
    'omni.agent.worldsurveyor',
    'omni.agent.worldrecorder',
    'omni.agent.worldstreamer.rtmp',
    'omni.agent.worldstreamer.srt'
  )
  foreach ($name in $exts) {
    $src = Join-Path $srcBase $name
    $dst = Join-Path $extsUser $name
    if (Test-Path $dst) { Write-Host "Exists: $dst (skipping)"; continue }
    if (Test-Path $src) {
      New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
      Write-Host "Linked: $dst -> $src"
    }
  }
  Invoke-PrecompileExtensions
}

# Create launcher
if (Read-Choice "Create an Isaac Sim launcher script?" $true) {
  $launcher = Join-Path (Split-Path $PSScriptRoot -Parent) "scripts/launch_agent_world.ps1"
  New-Item -ItemType Directory -Force -Path (Split-Path $launcher -Parent) | Out-Null

  # Find an Isaac launch script
  $cands = @(
    (Join-Path $IsaacDir 'isaac-sim.xr.vr.bat'),
    (Join-Path $IsaacDir 'isaac-sim.xr.bat'),
    (Join-Path $IsaacDir 'isaac-sim.bat')
  )
  $bin = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $bin) { Write-Warning "Could not find Isaac launcher .bat in $IsaacDir" }

  @"
Param([string[]]
  $Args)


$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $RepoRoot '.env'
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#') { return }
    if ($_ -match '^\s*$') { return }
    $kv = $_.Split('=',2)
    if ($kv.Count -eq 2) { $k=$kv[0]; $v=$kv[1]; $env:$k=$v }
  }
}

Write-Host "Launching Isaac Sim with Agent World extensions"

$IsaacDir = "$IsaacDir"
$ExtsUser = "$extsUser"
$Bin = "$bin"

& $Bin --ext-folder "$ExtsUser" `
  --enable omni.agent.worldbuilder `
  --enable omni.agent.worldviewer `
  --enable omni.agent.worldsurveyor `
  --enable omni.agent.worldrecorder `
  --enable omni.agent.worldstreamer.srt `
  --/exts/omni.agent.worldbuilder/auth_enabled=true `
  --/exts/omni.agent.worldviewer/auth_enabled=true `
  --/exts/omni.agent.worldsurveyor/auth_enabled=false `
  --/exts/omni.agent.worldrecorder/auth_enabled=true `
  --/exts/omni.agent.worldstreamer.srt/auth_enabled=true `
  @Args
"@ | Set-Content -LiteralPath $launcher -NoNewline:$false

  Write-Host "Launcher created: $launcher"
}

Write-Host "==> Done. You can run scripts/launch_agent_world.ps1 to start Isaac Sim." -ForegroundColor Green
