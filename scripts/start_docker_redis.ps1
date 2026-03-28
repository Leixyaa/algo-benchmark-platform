param(
  [string]$ContainerName = "algo-redis",
  [int]$Port = 6379,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-Command([string]$Name) {
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-ListeningPid([int]$LocalPort) {
  try {
    $conn = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return $conn.OwningProcess }
  } catch {
  }
  return $null
}

function Start-DockerDesktopIfFound {
  $candidates = @()
  if ($env:ProgramFiles) {
    $candidates += (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
  }
  if ($env:LocalAppData) {
    $candidates += (Join-Path $env:LocalAppData "Programs\Docker\Docker\Docker Desktop.exe")
  }
  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) {
      Write-Host "Starting Docker Desktop..."
      if (-not $DryRun) {
        Start-Process -FilePath $p | Out-Null
      }
      return $true
    }
  }
  return $false
}

function Wait-DockerReady {
  if ($DryRun) { return $true }
  for ($i = 0; $i -lt 60; $i++) {
    try {
      & docker info 1>$null 2>$null
      return $true
    } catch {
      Start-Sleep -Seconds 2
    }
  }
  return $false
}

if (Get-ListeningPid $Port) {
  Write-Host "Redis is already listening on $Port."
  exit 0
}

if (-not (Test-Command "docker")) {
  Write-Host "Docker command not found. Please install Docker Desktop."
  exit 1
}

$dockerReady = $false
try {
  if (-not $DryRun) {
    & docker info 1>$null 2>$null
  }
  $dockerReady = $true
} catch {
  $null = Start-DockerDesktopIfFound
  $dockerReady = Wait-DockerReady
}

if (-not $dockerReady) {
  Write-Host "Docker daemon is not ready."
  exit 1
}

$exists = $false
$running = $false
if (-not $DryRun) {
  $id = (& docker ps -a --filter "name=^/$ContainerName$" --format "{{.ID}}" 2>$null | Select-Object -First 1)
  if ($id) { $exists = $true }
  $rid = (& docker ps --filter "name=^/$ContainerName$" --format "{{.ID}}" 2>$null | Select-Object -First 1)
  if ($rid) { $running = $true }
}

if ($DryRun) {
  Write-Host "docker ps -a --filter name=^/$ContainerName$ --format {{.ID}}"
  Write-Host "docker ps --filter name=^/$ContainerName$ --format {{.ID}}"
  Write-Host "docker start $ContainerName  (if exists and stopped)"
  Write-Host "docker run --name $ContainerName -p ${Port}:6379 -d redis:7  (if not exists)"
  exit 0
}

if ($running) {
  Write-Host "Redis container is already running: $ContainerName"
} elseif ($exists) {
  Write-Host "Starting existing Redis container: $ContainerName"
  & docker start $ContainerName | Out-Null
} else {
  Write-Host "Creating Redis container: $ContainerName"
  & docker run --name $ContainerName -p "${Port}:6379" -d redis:7 | Out-Null
}

for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 250
  if (Get-ListeningPid $Port) {
    Write-Host "Redis is ready at 127.0.0.1:$Port"
    exit 0
  }
}

Write-Host "Redis did not become ready on port $Port."
exit 1
