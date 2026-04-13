param(
  [switch]$SkipRedis,
  [switch]$UseMySQL,
  [switch]$DryRun,
  [ValidateRange(1, 16)]
  [int]$WorkerCount = 1
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

function Get-EdgePath {
  $candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
  ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
  return $candidates | Select-Object -First 1
}

function Get-FileUri([string]$PathText) {
  return ([System.Uri]$PathText).AbsoluteUri
}

$repoRoot = Get-RepoRoot
$desktopDir = Join-Path $repoRoot "desktop"
$webDir = Join-Path $repoRoot "web"
$backendDir = Join-Path $repoRoot "backend"
$venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
$redisScript = Join-Path $repoRoot "scripts\start_docker_redis.ps1"
$mysqlScript = Join-Path $repoRoot "scripts\start_docker_mysql.ps1"
$electronExe = Join-Path $desktopDir "node_modules\electron\dist\electron.exe"
$edgeExe = Get-EdgePath
$desktopIndex = Join-Path $webDir "dist-desktop\index.html"
$desktopDataDir = Join-Path $backendDir "data\desktop"
$desktopDbPath = Join-Path $desktopDataDir "abp-desktop.db"
$mySqlRootPassword = $env:ABP_MYSQL_ROOT_PASSWORD

if ([string]::IsNullOrWhiteSpace($mySqlRootPassword)) {
  $mySqlRootPassword = "abp_mysql_123456"
}

if (-not (Test-Path -LiteralPath $desktopDir)) {
  Write-Host "Desktop directory not found: $desktopDir"
  exit 1
}
if (-not (Test-Path -LiteralPath $webDir)) {
  Write-Host "Web directory not found: $webDir"
  exit 1
}
if (-not (Test-Path -LiteralPath $venvPy)) {
  Write-Host "Python venv not found: $venvPy"
  exit 1
}
if (-not (Test-Path -LiteralPath $redisScript)) {
  Write-Host "Redis startup script not found: $redisScript"
  exit 1
}
if (-not (Test-Path -LiteralPath $mysqlScript)) {
  Write-Host "MySQL startup script not found: $mysqlScript"
  exit 1
}
if (-not (Test-Path -LiteralPath $desktopDataDir)) {
  if ($DryRun) {
    Write-Host "Creating desktop data directory"
    Write-Host "  mkdir $desktopDataDir"
  } else {
    New-Item -ItemType Directory -Path $desktopDataDir -Force | Out-Null
  }
}

if (-not $SkipRedis) {
  if ($DryRun) {
    & $redisScript -DryRun
  } else {
    & $redisScript
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to prepare Redis."
    exit 1
  }
}

if ($UseMySQL) {
  if ($DryRun) {
    & $mysqlScript -DryRun
  } else {
    & $mysqlScript
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to prepare MySQL."
    exit 1
  }
}

Write-Host "Building desktop frontend"
if ($DryRun) {
  Write-Host "  cd $webDir"
  Write-Host "  npm run build:desktop"
} else {
  Push-Location $webDir
  try {
    & npm run build:desktop
  } finally {
    Pop-Location
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build desktop frontend."
    exit 1
  }
}

if (Test-Path -LiteralPath $electronExe) {
  $desktopDbMode = if ($UseMySQL) { "mysql" } else { "sqlite" }
  Start-ServiceWindow `
    -Title "ABP - Desktop" `
    -WorkingDir $desktopDir `
    -CommandText "`$env:ABP_DESKTOP_WORKER_COUNT = '$WorkerCount'`r`n`$env:ABP_DESKTOP_DB_MODE = '$desktopDbMode'`r`nnpm start"
} elseif ($edgeExe) {
  Write-Host "Electron runtime not found. Falling back to Edge app mode."
  $desktopUri = Get-FileUri $desktopIndex
  $desktopSqlUrl = if ($UseMySQL) {
    $encodedMySqlRootPassword = [Uri]::EscapeDataString($mySqlRootPassword)
    "mysql+pymysql://root:${encodedMySqlRootPassword}@127.0.0.1:3306/algo_benchmark?charset=utf8mb4"
  } else {
    $desktopDbPathNormalized = $desktopDbPath -replace "\\", "/"
    "sqlite:///$desktopDbPathNormalized"
  }
  $desktopEnv = @(
    "`$env:ABP_SQL_STORE_URL = '$desktopSqlUrl'"
    "`$env:ABP_SQL_FALLBACK_REDIS = '1'"
  ) -join "`r`n"
  if ($DryRun) {
    Write-Host "Starting ABP - Backend API"
    Write-Host "  cd $backendDir"
    Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
    for ($i = 1; $i -le $WorkerCount; $i++) {
      Write-Host "Starting ABP - Worker $i"
      Write-Host "  cd $backendDir"
      Write-Host "  .\.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker -P solo -l info -n desktop_worker_$i"
    }
    Write-Host "Starting ABP - Desktop (Edge App Mode)"
    Write-Host "  $edgeExe --app=$desktopUri --window-size=1440,920"
  } else {
    Start-ServiceWindow `
      -Title "ABP - Backend API" `
      -WorkingDir $backendDir `
      -CommandText "$desktopEnv`r`n.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
    for ($i = 1; $i -le $WorkerCount; $i++) {
      Start-ServiceWindow `
        -Title "ABP - Worker $i" `
        -WorkingDir $backendDir `
        -CommandText "$desktopEnv`r`n.\.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker -P solo -l info -n desktop_worker_$i"
    }
    Start-Process -FilePath $edgeExe -ArgumentList "--app=$desktopUri", "--window-size=1440,920" | Out-Null
  }
} else {
  Write-Host "Neither Electron nor Microsoft Edge is available."
  Write-Host "To use Electron later, run: cd desktop; npm install"
  exit 1
}

Write-Host ""
Write-Host "Desktop launcher started."
Write-Host "Preferred desktop shell: Electron"
Write-Host "Fallback desktop shell: Microsoft Edge app mode"
Write-Host "Desktop database mode: $(if ($UseMySQL) { 'MySQL' } else { 'SQLite' })"
