[CmdletBinding()]
param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$composeFile = Join-Path $repoRoot "docker-compose.yml"

if (-not (Test-Path -LiteralPath $backendDir)) {
    throw "Khong tim thay backend: $backendDir"
}

if (-not (Test-Path -LiteralPath $frontendDir)) {
    throw "Khong tim thay frontend: $frontendDir"
}

function Get-ExecutablePath {
    param( 
        [string[]]$Candidates
    )

    foreach ($name in $Candidates) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    throw "Khong tim thay lenh: $($Candidates -join ', ')"
}

$terminalExe = Get-ExecutablePath @("pwsh", "powershell")
$pythonExe = Get-ExecutablePath @("py", "python")
$npmExe = Get-ExecutablePath @("npm.cmd", "npm")

# ── Docker ──────────────────────────────────────────────────────────

if (-not $SkipDocker -and (Test-Path -LiteralPath $composeFile)) {
    $dockerExe = Get-ExecutablePath @("docker")
    & $dockerExe compose -f $composeFile up -d
}

# ── Backend (FastAPI) ───────────────────────────────────────────────

$backendCommand = @"
Set-Location -LiteralPath `"$backendDir`"
Write-Host '=== EnvChat Backend ===' -ForegroundColor Green
Write-Host 'Starting FastAPI on http://localhost:8080 ...'
& `"$pythonExe`" -m uvicorn app.api:app --reload --host 0.0.0.0 --port 8080
"@

$backendBytes = [System.Text.Encoding]::Unicode.GetBytes($backendCommand)
$backendEncoded = [Convert]::ToBase64String($backendBytes)

Start-Process -FilePath $terminalExe -ArgumentList @(
    "-NoExit",
    "-EncodedCommand",
    $backendEncoded
)

# ── Frontend (Next.js) ──────────────────────────────────────────────

$frontendCommand = @"
Set-Location -LiteralPath `"$frontendDir`"
Write-Host '=== EnvChat Frontend ===' -ForegroundColor Cyan
Write-Host 'Starting Next.js on http://localhost:3000 ...'
& `"$npmExe`" run dev
"@

$frontendBytes = [System.Text.Encoding]::Unicode.GetBytes($frontendCommand)
$frontendEncoded = [Convert]::ToBase64String($frontendBytes)

Start-Process -FilePath $terminalExe -ArgumentList @(
    "-NoExit",
    "-EncodedCommand",
    $frontendEncoded
)

# ── Summary ─────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Da mo backend va frontend trong 2 cua so rieng." -ForegroundColor Green
if (-not $SkipDocker -and (Test-Path -LiteralPath $composeFile)) {
    Write-Host "Docker services: mongodb, chromadb" -ForegroundColor Yellow
}
Write-Host "Backend:  http://localhost:8080/api/health" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
