Param(
  [Alias('Dest')]
  [string]$IsaacDir,
  [string]$Version = "5.0.0",
  [string]$ZipUrl
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

Write-Host "==> Agent World Installer (Windows)" -ForegroundColor Cyan

if (-not $IsaacDir) {
  $hasIsaac = Read-Choice "Is Isaac Sim already installed locally?" $true
  if ($hasIsaac) {
    $default = "$HOME/agent-world-prod/isaac-sim-host-$Version"
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
    "# Optional per-service overrides",
    "# AGENT_WORLDBUILDER_AUTH_TOKEN=$token",
    "# AGENT_WORLDBUILDER_HMAC_SECRET=$secret",
    "# AGENT_WORLDVIEWER_AUTH_TOKEN=$token",
    "# AGENT_WORLDVIEWER_HMAC_SECRET=$secret",
    "# AGENT_WORLDSURVEYOR_AUTH_TOKEN=$token",
    "# AGENT_WORLDSURVEYOR_HMAC_SECRET=$secret",
    "# AGENT_WORLDRECORDER_AUTH_TOKEN=$token",
    "# AGENT_WORLDRECORDER_HMAC_SECRET=$secret"
  ) -NoNewline:$false
  Write-Host "Wrote secrets to: $envPath"
}

# Link extensions into extsUser via Junctions
$defaultExts = Join-Path $IsaacDir "extsUser"
$extsUser = Read-Host "Enter extsUser path for extensions [$defaultExts]"
if (-not $extsUser) { $extsUser = $defaultExts }
if (-not (Test-Path $extsUser)) { New-Item -ItemType Directory -Path $extsUser | Out-Null }

if (Read-Choice "Create links for Agent World extensions into '$extsUser'?" $true) {
  $repoRoot = Split-Path $PSScriptRoot -Parent
  $srcBase = Join-Path $repoRoot "agentworld-extensions"
  $exts = @('omni.agent.worldbuilder','omni.agent.worldviewer','omni.agent.worldsurveyor','omni.agent.worldrecorder')
  foreach ($name in $exts) {
    $src = Join-Path $srcBase $name
    $dst = Join-Path $extsUser $name
    if (Test-Path $dst) { Write-Host "Exists: $dst (skipping)"; continue }
    if (Test-Path $src) {
      New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
      Write-Host "Linked: $dst -> $src"
    }
  }
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
  --/exts/omni.agent.worldbuilder/auth_enabled=true `
  --/exts/omni.agent.worldviewer/auth_enabled=true `
  --/exts/omni.agent.worldsurveyor/auth_enabled=false `
  --/exts/omni.agent.worldrecorder/auth_enabled=true `
  @Args
"@ | Set-Content -LiteralPath $launcher -NoNewline:$false

  Write-Host "Launcher created: $launcher"
}

Write-Host "==> Done. You can run scripts/launch_agent_world.ps1 to start Isaac Sim." -ForegroundColor Green
