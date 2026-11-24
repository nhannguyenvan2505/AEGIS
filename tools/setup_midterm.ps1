[CmdletBinding()]
param(
    [switch]$IncludeImageAI,
    [string]$CheckpointPath,
    [switch]$SkipInstall,
    [ValidateRange(1024,65535)][int]$MySqlPort = 3307,
    [ValidateRange(1024,65535)][int]$MongoPort = 27018,
    [ValidatePattern('^[a-z0-9][a-z0-9-]+$')][string]$DatabaseProject = 'aegis-database-dev'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    function Invoke-Checked {
        param([string]$Executable, [string[]]$TaskArguments)
        & $Executable @TaskArguments
        if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable (exit $LASTEXITCODE)" }
    }
    if (-not $SkipInstall) {
        foreach ($component in @('backend','forecast_demo')) {
            $pythonPath = Join-Path $projectRoot "$component/.venv/Scripts/python.exe"
            if (-not (Test-Path -LiteralPath $pythonPath)) {
                Invoke-Checked -Executable 'py' -TaskArguments @('-3.11','-m','venv',"$component/.venv")
            }
            Invoke-Checked -Executable $pythonPath -TaskArguments @('-m','pip','install','-r',"$component/requirements.txt")
        }
        if ($IncludeImageAI) {
            $imagePython = Join-Path $projectRoot 'ai_service/.venv/Scripts/python.exe'
            if (-not (Test-Path -LiteralPath $imagePython)) {
                Invoke-Checked -Executable 'py' -TaskArguments @('-3.11','-m','venv','ai_service/.venv')
            }
            Invoke-Checked -Executable $imagePython -TaskArguments @('-m','pip','install','-r','ai_service/api/requirements.txt')
        }
    }
    $environmentPath = Join-Path $projectRoot 'backend/database/.env'
    if (-not (Test-Path -LiteralPath $environmentPath)) {
        $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $lines = @()
            foreach ($key in @('AEGIS_MYSQL_ROOT_PASSWORD','AEGIS_MYSQL_PASSWORD','AEGIS_MONGO_ROOT_PASSWORD','AEGIS_MONGO_PASSWORD')) {
                $buffer = New-Object byte[] 32
                $generator.GetBytes($buffer)
                $lines += $key + '=' + ([BitConverter]::ToString($buffer).Replace('-','').ToLowerInvariant())
            }
            $lines += "AEGIS_MYSQL_PORT=$MySqlPort"
            $lines += "AEGIS_MONGO_PORT=$MongoPort"
            $lines += "COMPOSE_PROJECT_NAME=$DatabaseProject"
            [IO.File]::WriteAllLines($environmentPath,$lines)
        } finally { $generator.Dispose() }
        Write-Host 'Created local database configuration with random passwords.'
    }
    Invoke-Checked -Executable 'docker' -TaskArguments @('compose','--env-file','backend/database/.env','-f','backend/database/compose.yaml','up','-d','--wait','--wait-timeout','240')
    $backendPython = Join-Path $projectRoot 'backend/.venv/Scripts/python.exe'
    Invoke-Checked -Executable $backendPython -TaskArguments @('backend/database/apply_core_runtime.py')
    Invoke-Checked -Executable $backendPython -TaskArguments @('backend/database/apply_hybrid.py')
    Invoke-Checked -Executable $backendPython -TaskArguments @('backend/database/apply_farm_hierarchy.py')
    if ($IncludeImageAI) {
        $modelArguments = @('tools/provision_midterm_model.py')
        if ($CheckpointPath) { $modelArguments += @('--source',$CheckpointPath) }
        Invoke-Checked -Executable $backendPython -TaskArguments $modelArguments
    }
    Write-Host 'Database and midterm environments are ready.'
    Write-Host 'Guide: docs/MIDTERM_TEAM_QUICKSTART.md'
} finally { Pop-Location }
