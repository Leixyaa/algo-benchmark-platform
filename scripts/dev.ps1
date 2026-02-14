param(
  [ValidateSet("up", "down", "restart")]
  [string]$Action = "restart",
  [switch]$SkipRedis,
  [switch]$SkipBackend,
  [switch]$SkipWorker,
  [switch]$SkipWeb,
  [switch]$InstallDeps,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptsDir = Split-Path -Parent $PSCommandPath
  $root = Resolve-Path (Join-Path $scriptsDir "..")
  return $root.Path
}

function Test-Command([string]$Name) {
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Ensure-Dir([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-ListeningPid([int]$Port) {
  try {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
  } catch {
  }
  return $null
}

function Get-ProcessCommandLine([int]$ProcessId) {
  try {
    $p = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $ProcessId) -ErrorAction SilentlyContinue
    if ($p) { return $p.CommandLine }
  } catch {
  }
  return $null
}

function Stop-IfListeningMatchesRepo([string]$Name, [int]$Port, [string]$RepoRootPath) {
  $listeningPid = Get-ListeningPid $Port
  if (-not $listeningPid) { return $false }
  $cmd = Get-ProcessCommandLine $listeningPid
  if (-not $cmd) { return $false }

  $inRepo = $cmd -like ("*{0}*" -f $RepoRootPath)
  if (-not $inRepo) { return $false }

  Write-Host ("Stopping {0} by port {1} (pid {2})" -f $Name, $Port, $listeningPid)
  if (-not $DryRun) {
    Stop-Process -Id $listeningPid -Force -ErrorAction SilentlyContinue
  }
  return $true
}

function Read-Pid([string]$PidPath) {
  if (-not (Test-Path -LiteralPath $PidPath)) { return $null }
  $raw = (Get-Content -LiteralPath $PidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
  if (-not $raw) { return $null }
  $parsedPid = 0
  if ([int]::TryParse(($raw.Trim()), [ref]$parsedPid)) { return $parsedPid }
  return $null
}

function Stop-Pid([string]$Name, [string]$PidPath) {
  $procId = Read-Pid $PidPath
  if (-not $procId) { return }
  try {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p) {
      Write-Host ("Stopping {0} (pid {1})" -f $Name, $procId)
      if (-not $DryRun) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
      }
    }
  } finally {
    if (-not $DryRun) {
      Remove-Item -LiteralPath $PidPath -ErrorAction SilentlyContinue
    }
  }
}

function Start-ServiceWindow([string]$Name, [string]$Title, [string]$WorkingDir, [string]$InnerCommand, [string]$PidPath) {
  Write-Host ("Starting {0}..." -f $Name)
  if ($DryRun) {
    Write-Host ("  cd {0}" -f $WorkingDir)
    Write-Host ("  {0}" -f $InnerCommand)
    return
  }

  $cmd = @(
    "`$host.ui.RawUI.WindowTitle = '$Title'"
    "Set-Location -LiteralPath '$WorkingDir'"
    "`$env:PYTHONUTF8 = '1'"
    $InnerCommand
  ) -join "`r`n"

  $bytes = [Text.Encoding]::Unicode.GetBytes($cmd)
  $encoded = [Convert]::ToBase64String($bytes)
  $p = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-EncodedCommand", $encoded -WorkingDirectory $WorkingDir -PassThru
  Set-Content -LiteralPath $PidPath -Value $p.Id -Encoding ascii
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$webDir = Join-Path $repoRoot "web"
$stateDir = Join-Path $repoRoot "logs\\dev"
Ensure-Dir $stateDir

$pidRedis = Join-Path $stateDir "redis.pid"
$pidApi = Join-Path $stateDir "api.pid"
$pidWorker = Join-Path $stateDir "worker.pid"
$pidWeb = Join-Path $stateDir "web.pid"

function Test-BackendDeps([string]$PythonExe) {
  if (-not $PythonExe) { return $false }
  if (-not (Test-Path -LiteralPath $PythonExe)) { return $false }
  & $PythonExe -c "import fastapi,uvicorn,redis,celery" 1>$null 2>$null
  return ($LASTEXITCODE -eq 0)
}

function Ensure-BackendVenv {
  if (-not (Test-Command "python")) {
    return $null
  }

  $venvDir = Join-Path $backendDir ".venv"
  $venvPy = Join-Path $venvDir "Scripts\\python.exe"

  if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host "Creating backend venv (.venv)..."
    if ($DryRun) {
      Write-Host ("  cd {0}" -f $backendDir)
      Write-Host "  python -m venv .venv"
    } else {
      Push-Location $backendDir
      try {
        & python -m venv .venv
      } finally {
        Pop-Location
      }
    }
  }

  if ($InstallDeps -or -not (Test-BackendDeps $venvPy)) {
    Write-Host "Installing backend deps (venv)..."
    if ($DryRun) {
      Write-Host ("  cd {0}" -f $backendDir)
      Write-Host "  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
    } else {
      Push-Location $backendDir
      try {
        & $venvPy -m pip install -r requirements.txt
      } finally {
        Pop-Location
      }
    }
  }

  if (Test-Path -LiteralPath $venvPy) { return $venvPy }
  return $null
}

function Start-LocalRedis {
  if (-not (Test-Command "redis-server")) {
    return $false
  }
  Write-Host "Starting Redis (local redis-server)..."
  if ($DryRun) {
    Write-Host "  redis-server --port 6379"
    return $true
  }
  try {
    $p = Start-Process -FilePath "redis-server" -ArgumentList "--port", "6379" -PassThru
    Set-Content -LiteralPath $pidRedis -Value $p.Id -Encoding ascii
  } catch {
    return $false
  }
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 200
    if (Get-ListeningPid 6379) { return $true }
  }
  return $false
}

function Start-DockerDesktopIfAvailable {
  $candidates = @()
  if ($env:ProgramFiles) {
    $candidates += (Join-Path $env:ProgramFiles "Docker\\Docker\\Docker Desktop.exe")
  }
  if ($env:LocalAppData) {
    $candidates += (Join-Path $env:LocalAppData "Programs\\Docker\\Docker\\Docker Desktop.exe")
  }

  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) {
      Write-Host "Starting Docker Desktop..."
      if ($DryRun) {
        Write-Host ("  {0}" -f $p)
      } else {
        Start-Process -FilePath $p | Out-Null
      }
      return $true
    }
  }
  return $false
}

function Wait-DockerReady {
  if ($DryRun) { return $true }
  for ($i = 0; $i -lt 30; $i++) {
    try {
      & docker info 1>$null 2>$null
      return $true
    } catch {
    }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Up-Redis {
  if ($SkipRedis) { return $true }
  $listeningPid = Get-ListeningPid 6379
  if ($listeningPid) {
    Write-Host ("Redis ??? 6379 ???????pid {0}???????????????" -f $listeningPid)
    return $true
  }

  if (-not (Test-Command "docker")) {
    if (Start-LocalRedis) { return $true }
    Write-Host "Docker ?????????¦Ä??? redis-server???????????? Redis"
    Write-Host "????? 127.0.0.1:6379 ???¨²??????§³?"
    return $false
  }

  if (-not $DryRun) {
    try {
      & docker info 1>$null 2>$null
    } catch {
      $startedDesktop = Start-DockerDesktopIfAvailable
      if ($startedDesktop) {
        $null = Wait-DockerReady
      }
    }
  }

  if ($DryRun) {
    Write-Host "Ensuring Redis (docker container: algo-redis)..."
    Write-Host "  docker rm -f algo-redis 2>$null"
    Write-Host "  docker run --name algo-redis -p 6379:6379 -d redis:7"
    return $true
  }

  try {
    & docker info 1>$null 2>$null
  } catch {
    if (Start-LocalRedis) { return $true }
    Write-Host "Docker daemon ?????????¦Ä??? redis-server???????????? Redis"
    Write-Host "????? 127.0.0.1:6379 ???¨²??????§³?"
    return $false
  }

  Write-Host "Ensuring Redis (docker container: algo-redis)..."
  $started = $false
  for ($i = 0; $i -lt 8; $i++) {
    try {
      & docker rm -f algo-redis 2>$null | Out-Null
      & docker run --name algo-redis -p 6379:6379 -d redis:7 | Out-Null
      $started = $true
      break
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  if (-not $started) {
    Write-Host "Docker ???? Redis ???????? Docker Desktop ??????"
    return $false
  }

  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 200
    if (Get-ListeningPid 6379) { return $true }
  }
  Write-Host "Redis ?????????6379 ?????¦Ä????"
  return $false
}

function Down-Redis {
  if ($SkipRedis) { return }
  Stop-Pid -Name "Redis (local)" -PidPath $pidRedis
  if (-not (Test-Command "docker")) { return }
  if ($DryRun) {
    Write-Host "Stopping Redis (docker container: algo-redis)..."
    Write-Host "  docker rm -f algo-redis 2>$null"
    return
  }
  try {
    & docker info 1>$null 2>$null
    & docker rm -f algo-redis 2>$null | Out-Null
  } catch {
    Write-Host "Docker ????????????? Redis ????"
  }
}

function Maybe-Install {
  $needWebInstall = $InstallDeps -or (-not (Test-Path -LiteralPath (Join-Path $webDir "node_modules")))

  if (-not $SkipBackend -or -not $SkipWorker) {
    $null = Ensure-BackendVenv
  }

  if (-not $SkipWeb -and $needWebInstall) {
    if (-not (Test-Command "npm")) {
      Write-Host "npm ?????????????????????"
    } else {
      Write-Host "Installing web deps..."
      if ($DryRun) {
        Write-Host ("  cd {0}" -f $webDir)
        Write-Host "  npm install"
      } else {
        Push-Location $webDir
        try {
          & npm install
        } finally {
          Pop-Location
        }
      }
    }
  }
}

function Up-Services {
  Maybe-Install
  $redisOk = Up-Redis
  if (-not $redisOk) {
    if (-not $SkipBackend -or -not $SkipWorker) {
      Write-Host ""
      Write-Host "Redis ¦Ä???????????????????????? Backend/Worker ????????????"
      Write-Host "??????????? Docker Desktop ??? Redis??????? -SkipBackend/-SkipWorker ??????????"
      exit 1
    }
  }

  $backendPy = $null
  if (-not $SkipBackend -or -not $SkipWorker) {
    $backendPy = Ensure-BackendVenv
    if (-not $backendPy) {
      Write-Host ""
      Write-Host "?????????¦Ä????????????? Backend/Worker??"
      exit 1
    }
  }

  $apiLog = Join-Path $stateDir "api.log"
  $workerLog = Join-Path $stateDir "worker.log"
  $webLog = Join-Path $stateDir "web.log"

  if (-not $SkipBackend) {
    $pid8000 = Get-ListeningPid 8000
    if ($pid8000) {
      $null = Stop-IfListeningMatchesRepo -Name "Backend API" -Port 8000 -RepoRootPath $repoRoot
    }

    if (Get-ListeningPid 8000) {
      Write-Host ("??? 8000 ???????pid {0}???????????? Backend API" -f (Get-ListeningPid 8000))
    } else {
      Start-ServiceWindow `
        -Name "Backend API" `
        -Title "ABP - API (uvicorn)" `
        -WorkingDir $backendDir `
        -InnerCommand ('"{0}" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 2>&1 | Tee-Object -FilePath ''{1}''' -f $backendPy, $apiLog) `
        -PidPath $pidApi
    }
  }

  if (-not $SkipWorker) {
    Start-ServiceWindow `
      -Name "Celery Worker" `
      -Title "ABP - Worker (celery)" `
      -WorkingDir $backendDir `
      -InnerCommand ('"{0}" -m celery -A app.celery_app.celery_app worker -l info -P solo 2>&1 | Tee-Object -FilePath ''{1}''' -f $backendPy, $workerLog) `
      -PidPath $pidWorker
  }

  if (-not $SkipWeb) {
    $pid5173 = Get-ListeningPid 5173
    if ($pid5173) {
      $null = Stop-IfListeningMatchesRepo -Name "Web (Vite)" -Port 5173 -RepoRootPath $repoRoot
    }

    if (Get-ListeningPid 5173) {
      Write-Host ("??? 5173 ???????pid {0}???????????? Web" -f (Get-ListeningPid 5173))
    } else {
      Start-ServiceWindow `
        -Name "Web (Vite)" `
        -Title "ABP - Web (vite)" `
        -WorkingDir $webDir `
        -InnerCommand ('npm run dev 2>&1 | Tee-Object -FilePath ''{0}''' -f $webLog) `
        -PidPath $pidWeb
    }
  }

  Write-Host ""
  Write-Host "URLs:"
  Write-Host "  Backend health:  http://127.0.0.1:8000/health"
  Write-Host "  Backend docs:    http://127.0.0.1:8000/docs"
  Write-Host "  Frontend:        http://localhost:5173/"
  Write-Host ""
  Write-Host "Logs:"
  Write-Host ("  API:     {0}" -f (Join-Path $stateDir "api.log"))
  Write-Host ("  Worker:  {0}" -f (Join-Path $stateDir "worker.log"))
  Write-Host ("  Web:     {0}" -f (Join-Path $stateDir "web.log"))
}

function Down-Services {
  Stop-Pid -Name "Web (Vite)" -PidPath $pidWeb
  Stop-Pid -Name "Celery Worker" -PidPath $pidWorker
  Stop-Pid -Name "Backend API" -PidPath $pidApi
  $null = Stop-IfListeningMatchesRepo -Name "Web (Vite)" -Port 5173 -RepoRootPath $repoRoot
  $null = Stop-IfListeningMatchesRepo -Name "Backend API" -Port 8000 -RepoRootPath $repoRoot
  Down-Redis
}

if ($Action -eq "down") {
  Down-Services
  exit 0
}

if ($Action -eq "restart") {
  Down-Services
}

Up-Services
