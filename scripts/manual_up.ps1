param(
  [switch]$SkipRedis,
  [switch]$SkipMySQL,
  [switch]$DryRun,
  [ValidateRange(1, 16)]
  [int]$WorkerCount = 2,
  [string]$MySqlContainerName = "algo-mysql",
  [int]$MySqlPort = 3306,
  [string]$MySqlDatabase = "algo_benchmark",
  [string]$MySqlRootPassword = ""
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
$mysqlScript = Join-Path (Split-Path -Parent $PSCommandPath) "start_docker_mysql.ps1"

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

if (-not $SkipMySQL) {
  if (-not (Test-Path -LiteralPath $mysqlScript)) {
    Write-Host "MySQL startup script not found: $mysqlScript"
    exit 1
  }
  if ([string]::IsNullOrWhiteSpace($MySqlRootPassword)) {
    $MySqlRootPassword = $env:ABP_MYSQL_ROOT_PASSWORD
  }
  if ([string]::IsNullOrWhiteSpace($MySqlRootPassword)) {
    $MySqlRootPassword = "abp_mysql_123456"
  }
  if ($DryRun) {
    & $mysqlScript -DryRun -ContainerName $MySqlContainerName -Port $MySqlPort -Database $MySqlDatabase -RootPassword $MySqlRootPassword
  } else {
    & $mysqlScript -ContainerName $MySqlContainerName -Port $MySqlPort -Database $MySqlDatabase -RootPassword $MySqlRootPassword
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start Docker MySQL."
    exit 1
  }
  $encodedMySqlRootPassword = [Uri]::EscapeDataString($MySqlRootPassword)
  $env:ABP_SQL_STORE_URL = "mysql+pymysql://root:${encodedMySqlRootPassword}@127.0.0.1:${MySqlPort}/${MySqlDatabase}?charset=utf8mb4"
  if ([string]::IsNullOrWhiteSpace($env:ABP_SQL_FALLBACK_REDIS)) {
    $env:ABP_SQL_FALLBACK_REDIS = "1"
  }
}

Start-ServiceWindow `
  -Title "ABP - Backend API" `
  -WorkingDir $backendDir `
  -CommandText '.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001'

for ($i = 1; $i -le $WorkerCount; $i++) {
  Start-ServiceWindow `
    -Title "ABP - Worker $i" `
    -WorkingDir $backendDir `
    -CommandText ".\.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker -P solo -l info -n worker$i@%COMPUTERNAME%"
}

Start-ServiceWindow `
  -Title "ABP - Web" `
  -WorkingDir $webDir `
  -CommandText 'npm run dev'

Write-Host ""
Write-Host "Started services:"
Write-Host "  Redis:   127.0.0.1:6379"
if (-not $SkipMySQL) {
  Write-Host "  MySQL:   127.0.0.1:$MySqlPort/$MySqlDatabase"
}
Write-Host "  Backend: http://127.0.0.1:8001/docs"
Write-Host "  Workers: $WorkerCount"
Write-Host "  Web:     http://localhost:5173/"
