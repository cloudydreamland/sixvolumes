$ErrorActionPreference = 'Stop'
$auditRoot = $PSScriptRoot
$auditPython = Join-Path $auditRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $auditPython)) { throw 'Create .venv and install requirements.lock.txt first.' }
$env:SIXVOLUMES_RESULTS = 'results_replay_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
& $auditPython (Join-Path $auditRoot 'run.py') all
if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed; partial outputs retained in the replay directory.' }
Write-Output ('Replay results: ' + (Join-Path $auditRoot $env:SIXVOLUMES_RESULTS))
