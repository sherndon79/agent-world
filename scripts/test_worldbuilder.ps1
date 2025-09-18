Param(
  [string]$IsaacDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'isaac-sim-host-5.0.0'),
  [string[]]$PytestArgs
)

$PythonBat = Join-Path $IsaacDir 'python.bat'
if (-not (Test-Path $PythonBat)) {
  throw "Isaac Sim python.bat not found at $PythonBat"
}

$env:PYTHONPATH = "$(Join-Path (Split-Path $PSScriptRoot -Parent) 'agentworld-extensions');$($env:PYTHONPATH)"

$pytestInstalled = & $PythonBat -m pip show pytest >/dev/null 2>&1
if (-not $?) {
  Write-Host "==> Installing pytest into Isaac Sim Python"
  & $PythonBat -m pip install --upgrade pip | Out-Null
  & $PythonBat -m pip install pytest | Out-Null
}

& $PythonBat -m pytest (Join-Path (Split-Path $PSScriptRoot -Parent) 'agentworld-extensions/tests/worldbuilder') @PytestArgs
