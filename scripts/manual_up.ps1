param(
  [switch]$SkipRedis,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptsDir = Split-Path -Parent $PSCommandPath
  $root = Resolve-Path (Join-Path $scriptsDir "..")
  return $root.Path
}

function Start-ServiceWindow([string]$Title, [string]$WorkingDir, [string]$CommandText) {
  Write-Host "Starting $Title"
  if ($DryRun) {
    Write-Host "  cd $WorkingDir"
    Write-Host "  $CommandText"
    return
  }
  $cmd = @(
    "`$host.ui.RawUI.WindowTitle = '$Title'"
    "Set-Location -LiteralPath '$WorkingDir'"
    $CommandText
  ) -join "`r`n"
  $bytes = [Text.Encoding]::Unicode.GetBytes($cmd)
  $encoded = [Convert]::ToBase64String($bytes)
  Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-EncodedCommand", $encoded -WorkingDirectory $WorkingDir | Out-Null
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$webDir = Join-Path $repoRoot "web"
$venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
$redisScript = Join-Path (Split-Path -Parent $PSCommandPath) "start_docker_redis.ps1"

if (-not (Test-Path -LiteralPath $backendDir)) {
  Write-Host "Backend directory not found: $backendDir"
  exit 1
}
if (-not (Test-Path -LiteralPath $webDir)) {
  Write-Host "Web directory not found: $webDir"
  exit 1
}
if (-not (Test-Path -LiteralPath $venvPy)) {
  Write-Host "Python venv not found: $venvPy"
  Write-Host "Please prepare venv first: cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
  exit 1
}

if (-not $SkipRedis) {
  if (-not (Test-Path -LiteralPath $redisScript)) {
    Write-Host "Redis startup script not found: $redisScript"
    exit 1
  }
  if ($DryRun) {
    & $redisScript -DryRun
  } else {
    & $redisScript
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start Docker Redis."
    exit 1
  }
}

Start-ServiceWindow `
  -Title "ABP - Backend API" `
  -WorkingDir $backendDir `
  -CommandText '.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000'

Start-ServiceWindow `
  -Title "ABP - Worker" `
  -WorkingDir $backendDir `
  -CommandText '.\.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker -P solo -l info'

Start-ServiceWindow `
  -Title "ABP - Web" `
  -WorkingDir $webDir `
  -CommandText 'npm run dev'

Write-Host ""
Write-Host "Started services:"
Write-Host "  Redis:   127.0.0.1:6379"
Write-Host "  Backend: http://127.0.0.1:8000/docs"
Write-Host "  Web:     http://localhost:5173/"
