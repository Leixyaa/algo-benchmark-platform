param(
  [switch]$StopRedis,
  [string]$ContainerName = "algo-redis",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptsDir = Split-Path -Parent $PSCommandPath
  $root = Resolve-Path (Join-Path $scriptsDir "..")
  return $root.Path
}

function Get-ProcessCommandLineMap {
  $map = @{}
  try {
    $items = @()
    try {
      $items = Get-CimInstance Win32_Process -ErrorAction Stop
    } catch {
      $items = Get-WmiObject Win32_Process -ErrorAction Stop
    }
    foreach ($item in ($items | Where-Object { $null -ne $_ })) {
      $cmd = ""
      if ($null -ne $item.CommandLine) {
        $cmd = [string]$item.CommandLine
      }
      $map[[int]$item.ProcessId] = $cmd
    }
  } catch {
  }
  return $map
}

function Stop-ProcessList([System.Collections.Generic.List[int]]$Ids, [string]$Label) {
  $uniqueIds = $Ids | Sort-Object -Unique
  if (-not $uniqueIds -or $uniqueIds.Count -eq 0) {
    Write-Host "No $Label processes found."
    return
  }

  Write-Host "Stopping $Label processes: $($uniqueIds -join ', ')"
  if ($DryRun) {
    return
  }

  foreach ($id in $uniqueIds) {
    try {
      Stop-Process -Id $id -Force -ErrorAction Stop
    } catch {
      Write-Host "  Failed to stop PID $id : $($_.Exception.Message)"
    }
  }
}

function Add-IfMatch([System.Collections.Generic.List[int]]$Ids, $Proc, [string]$CommandLine, [string[]]$Needles) {
  $text = ""
  if ($null -ne $CommandLine) {
    $text = [string]$CommandLine
  }
  foreach ($needle in $Needles) {
    if ($text -like "*$needle*") {
      $Ids.Add([int]$Proc.Id)
      return
    }
  }
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$webDir = Join-Path $repoRoot "web"
$cmdLines = Get-ProcessCommandLineMap

$pythonIds = New-Object 'System.Collections.Generic.List[int]'
$nodeIds = New-Object 'System.Collections.Generic.List[int]'
$windowIds = New-Object 'System.Collections.Generic.List[int]'

$all = Get-Process -ErrorAction SilentlyContinue
foreach ($proc in $all) {
  $cmd = $cmdLines[[int]$proc.Id]
  if ($proc.ProcessName -eq "python") {
    Add-IfMatch $pythonIds $proc $cmd @(
      "$backendDir",
      "uvicorn app.main:app",
      "celery -A app.celery_app:celery_app worker"
    )
    continue
  }
  if ($proc.ProcessName -eq "node") {
    Add-IfMatch $nodeIds $proc $cmd @(
      "$webDir",
      "vite",
      "npm run dev"
    )
    continue
  }
  if ($proc.ProcessName -eq "powershell") {
    $title = ""
    if ($null -ne $proc.MainWindowTitle) {
      $title = [string]$proc.MainWindowTitle
    }
    if ($title -like "ABP -*") {
      $windowIds.Add([int]$proc.Id)
      continue
    }
    if (($cmd -like "*$repoRoot*") -and ($cmd -like "*manual_up.ps1*")) {
      $windowIds.Add([int]$proc.Id)
    }
  }
}

Stop-ProcessList $pythonIds "backend/worker"
Stop-ProcessList $nodeIds "web"
Stop-ProcessList $windowIds "ABP window"

if ($StopRedis) {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    Write-Host "Docker command not found, skip Redis container shutdown."
  } else {
    Write-Host "Stopping Redis container: $ContainerName"
    if (-not $DryRun) {
      try {
        & docker stop $ContainerName | Out-Null
      } catch {
        Write-Host "  Failed to stop Redis container: $($_.Exception.Message)"
      }
    }
  }
}

Write-Host "Done."
