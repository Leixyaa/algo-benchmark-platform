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

function Get-ProcessCommandLine([int]$Pid) {
  try {
    $p = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $Pid) -ErrorAction SilentlyContinue
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

  $cmd = @"
$host.ui.RawUI.WindowTitle = '$Title'
Set-Location -LiteralPath '$WorkingDir'
$env:PYTHONUTF8 = '1'
$InnerCommand
"@
  $bytes = [Text.Encoding]::Unicode.GetBytes($cmd)
  $encoded = [Convert]::ToBase64String($bytes)
  $p = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-EncodedCommand", $encoded -WorkingDirectory $WorkingDir -PassThru
  Set-Content -LiteralPath $PidPath -Value $p.Id -Encoding ascii
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$webDir = Join-Path $repoRoot "web"
$stateDir = Join-Path $repoRoot "logs\dev"
Ensure-Dir $stateDir

$pidApi = Join-Path $stateDir "api.pid"
$pidWorker = Join-Path $stateDir "worker.pid"
$pidWeb = Join-Path $stateDir "web.pid"

function Up-Redis {
  if ($SkipRedis) { return $true }
  $listeningPid = Get-ListeningPid 6379
  if ($listeningPid) {
    Write-Host ("Redis 端口 6379 已被占用（pid {0}），跳过自动启动" -f $listeningPid)
    return $true
  }
  if (-not (Test-Command "docker")) {
    Write-Host "Docker 未安装或不可用：跳过 Redis 自动启动（请确保本机 127.0.0.1:6379 可用）"
    return $false
  }
  Write-Host "Ensuring Redis (docker container: algo-redis)..."
  if ($DryRun) {
    Write-Host "  docker rm -f algo-redis 2>$null"
    Write-Host "  docker run --name algo-redis -p 6379:6379 -d redis:7"
    return $true
  }
  try {
    & docker info 1>$null 2>$null
  } catch {
    Write-Host "Docker 似乎未启动（Docker Desktop/daemon 不可用）：无法自动启动 Redis"
    Write-Host "请先启动 Docker Desktop，或自行启动本地 Redis（127.0.0.1:6379）后再运行。"
    return $false
  }

  try {
    & docker rm -f algo-redis 2>$null | Out-Null
    & docker run --name algo-redis -p 6379:6379 -d redis:7 | Out-Null
  } catch {
    Write-Host "Docker 命令执行失败：无法自动启动 Redis"
    Write-Host "请先启动 Docker Desktop，或自行启动本地 Redis（127.0.0.1:6379）后再运行。"
    return $false
  }

  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 200
    if (Get-ListeningPid 6379) { return $true }
  }
  Write-Host "Redis 启动超时：6379 端口仍未监听"
  return $false
}

function Down-Redis {
  if ($SkipRedis) { return }
  if (-not (Test-Command "docker")) { return }
  Write-Host "Stopping Redis (docker container: algo-redis)..."
  if ($DryRun) {
    Write-Host "  docker rm -f algo-redis 2>$null"
    return
  }
  try {
    & docker rm -f algo-redis 2>$null | Out-Null
  } catch {
    Write-Host "Docker 不可用（daemon 未启动或连接失败）：跳过停止 Redis 容器"
  }
}

function Maybe-Install {
  if (-not $InstallDeps) { return }

  if (-not (Test-Command "python")) {
    Write-Host "python 不可用：跳过后端依赖安装"
  } else {
    Write-Host "Installing backend deps..."
    if ($DryRun) {
      Write-Host ("  cd {0}" -f $backendDir)
      Write-Host "  python -m pip install -r requirements.txt"
    } else {
      Push-Location $backendDir
      try {
        & python -m pip install -r requirements.txt
      } finally {
        Pop-Location
      }
    }
  }

  if (-not (Test-Command "npm")) {
    Write-Host "npm 不可用：跳过前端依赖安装"
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

function Up-Services {
  Maybe-Install
  $redisOk = Up-Redis
  if (-not $redisOk) {
    if (-not $SkipBackend -or -not $SkipWorker) {
      Write-Host ""
      Write-Host "Redis 未就绪：已终止启动流程（避免 Backend/Worker 无法连接而持续报错）。"
      Write-Host "可选：先启动 Docker Desktop 或本地 Redis；或使用 -SkipBackend/-SkipWorker 临时只启前端。"
      exit 1
    }
  }

  if (-not $SkipBackend) {
    $pid8000 = Get-ListeningPid 8000
    if ($pid8000) {
      $stopped = Stop-IfListeningMatchesRepo -Name "Backend API" -Port 8000 -RepoRootPath $repoRoot
      $pid8000b = Get-ListeningPid 8000
      if ($pid8000b) {
        Write-Host ("端口 8000 已被占用（pid {0}），跳过启动 Backend API" -f $pid8000b)
      } else {
        Start-ServiceWindow `
          -Name "Backend API" `
          -Title "ABP - API (uvicorn)" `
          -WorkingDir $backendDir `
          -InnerCommand "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
          -PidPath $pidApi
      }
    } else {
    Start-ServiceWindow `
      -Name "Backend API" `
      -Title "ABP - API (uvicorn)" `
      -WorkingDir $backendDir `
      -InnerCommand "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
      -PidPath $pidApi
    }
  }

  if (-not $SkipWorker) {
    Start-ServiceWindow `
      -Name "Celery Worker" `
      -Title "ABP - Worker (celery)" `
      -WorkingDir $backendDir `
      -InnerCommand "python -m celery -A app.celery_app.celery_app worker -l info -P solo" `
      -PidPath $pidWorker
  }

  if (-not $SkipWeb) {
    $pid5173 = Get-ListeningPid 5173
    if ($pid5173) {
      $stopped = Stop-IfListeningMatchesRepo -Name "Web (Vite)" -Port 5173 -RepoRootPath $repoRoot
      $pid5173b = Get-ListeningPid 5173
      if ($pid5173b) {
        Write-Host ("端口 5173 已被占用（pid {0}），跳过启动 Web" -f $pid5173b)
      } else {
        Start-ServiceWindow `
          -Name "Web (Vite)" `
          -Title "ABP - Web (vite)" `
          -WorkingDir $webDir `
          -InnerCommand "npm run dev" `
          -PidPath $pidWeb
      }
    } else {
    Start-ServiceWindow `
      -Name "Web (Vite)" `
      -Title "ABP - Web (vite)" `
      -WorkingDir $webDir `
      -InnerCommand "npm run dev" `
      -PidPath $pidWeb
    }
  }

  Write-Host ""
  Write-Host "URLs:"
  Write-Host "  Backend health:  http://127.0.0.1:8000/health"
  Write-Host "  Backend docs:   http://127.0.0.1:8000/docs"
  Write-Host "  Frontend:       http://localhost:5173/"
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
