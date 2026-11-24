# Start the AEGIS AI service with the rice / non-rice gatekeeper enabled.
#   .\run_ai_service.ps1 [-Python D:\AEGIS-AI\.venv\Scripts\python.exe] [-Port 8000]
# Weights live in ai_service\experiments (git-ignored): detector baseline_v4_50epochs, gatekeeper gate_v1b.
param(
    [string]$Python = "D:\AEGIS-AI\.venv\Scripts\python.exe",
    [int]$Port = 8000
)
$root = $PSScriptRoot
if (-not $env:AEGIS_GATE_WEIGHTS) { $env:AEGIS_GATE_WEIGHTS = Join-Path $root "experiments\gatekeeper\gate_v1b\best.pt" }
if (-not (Test-Path $env:AEGIS_GATE_WEIGHTS)) { throw "Gatekeeper weights not found: $($env:AEGIS_GATE_WEIGHTS). Copy best.pt there or set AEGIS_GATE_WEIGHTS." }
if (-not (Test-Path $Python)) { throw "Python not found: $Python" }
$env:AEGIS_AI_PORT = "$Port"
Write-Host "Gatekeeper: $($env:AEGIS_GATE_WEIGHTS)  ->  http://127.0.0.1:$Port/v2/health"
& $Python -I (Join-Path $root "api\app.py")
