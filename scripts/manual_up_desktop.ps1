param(
  [switch]$SkipRedis,
  [switch]$SkipMySQL,
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

$repoRoot = Get-RepoRoot
$desktopDir = Join-Path $repoRoot "desktop"
$manualUpScript = Join-Path $repoRoot "scripts\manual_up.ps1"
$electronCli = Join-Path $desktopDir "node_modules\electron\cli.js"

if (-not (Test-Path -LiteralPath $desktopDir)) {
  Write-Host "Desktop directory not found: $desktopDir"
  exit 1
}

if (-not (Test-Path -LiteralPath $manualUpScript)) {
  Write-Host "manual_up.ps1 not found: $manualUpScript"
  exit 1
}

if (-not (Test-Path -LiteralPath $electronCli)) {
  Write-Host "Electron dependency not installed."
  Write-Host "Please run: cd desktop; npm install"
  exit 1
}

if ($SkipRedis -and $SkipMySQL -and $DryRun) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipRedis -SkipMySQL -DryRun
} elseif ($SkipRedis -and $SkipMySQL) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipRedis -SkipMySQL
} elseif ($SkipRedis -and $DryRun) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipRedis -DryRun
} elseif ($SkipMySQL -and $DryRun) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipMySQL -DryRun
} elseif ($SkipRedis) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipRedis
} elseif ($SkipMySQL) {
  & $manualUpScript -WorkerCount $WorkerCount -SkipMySQL
} elseif ($DryRun) {
  & $manualUpScript -WorkerCount $WorkerCount -DryRun
} else {
  & $manualUpScript -WorkerCount $WorkerCount
}
if ($LASTEXITCODE -ne 0) {
  Write-Host "Failed to start base services."
  exit 1
}

Start-ServiceWindow `
  -Title "ABP - Desktop" `
  -WorkingDir $desktopDir `
  -CommandText 'npm start'

Write-Host ""
Write-Host "Desktop launcher started."
Write-Host "If this is the first run, install Electron first: cd desktop; npm install"
