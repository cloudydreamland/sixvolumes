param([string]$Python = "python", [string]$Venv = ".venv")
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $ProjectRoot
try {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create venv; run python run.py directly instead." }
    $EnvironmentPython = Join-Path $Venv "Scripts\python.exe"
    & $EnvironmentPython -m pip install --no-index --find-links wheelhouse sixvolumes-trust-pipeline
    if ($LASTEXITCODE -ne 0) { throw "Offline installation failed." }
    & $EnvironmentPython -m sixvolumes demo -o outputs/offline-installed-demo
    if ($LASTEXITCODE -ne 0) { throw "Installed demo failed." }
} finally { Pop-Location }
