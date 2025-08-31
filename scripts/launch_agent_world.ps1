Param([string[]]$Args)

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

# Heuristic Isaac path discovery (same folder layout as installer default)
$Default = Join-Path $RepoRoot 'isaac-sim-host-5.0.0'
$IsaacDir = if (Test-Path $Default) { $Default } else { Read-Host "Enter Isaac Sim host path" }
$ExtsUser = Join-Path $IsaacDir 'extsUser'

$cands = @(
  (Join-Path $IsaacDir 'isaac-sim.xr.vr.bat'),
  (Join-Path $IsaacDir 'isaac-sim.xr.bat'),
  (Join-Path $IsaacDir 'isaac-sim.bat')
)
$Bin = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Bin) { throw "Could not find an Isaac Sim launcher .bat under $IsaacDir" }

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
