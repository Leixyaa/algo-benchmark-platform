param(
  [switch]$UseMySQL
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  $scriptsDir = Split-Path -Parent $PSCommandPath
  $root = Resolve-Path (Join-Path $scriptsDir "..")
  return $root.Path
}

function Copy-IfExists([string]$Source, [string]$Destination) {
  if (Test-Path -LiteralPath $Source) {
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
  }
}

function Get-FirstMatchPath([string]$Directory, [string]$Pattern) {
  $item = Get-ChildItem -LiteralPath $Directory -Filter $Pattern | Select-Object -First 1
  if (-not $item) {
    throw "Required file not found in $Directory matching $Pattern"
  }
  return $item.FullName
}

$repoRoot = Get-RepoRoot
$bundleRoot = Join-Path $repoRoot "release\desktop-runtime"
$bundleDocs = Join-Path $bundleRoot "docs"
$bundleScripts = Join-Path $bundleRoot "scripts"
$bundleDesktop = Join-Path $bundleRoot "desktop"
$bundleWeb = Join-Path $bundleRoot "web"

Write-Host "Building desktop frontend"
Push-Location (Join-Path $repoRoot "web")
try {
  & npm run build:desktop
} finally {
  Pop-Location
}
if ($LASTEXITCODE -ne 0) {
  Write-Host "Failed to build desktop frontend."
  exit 1
}

if (Test-Path -LiteralPath $bundleRoot) {
  Remove-Item -LiteralPath $bundleRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $bundleRoot, $bundleDocs, $bundleScripts, $bundleDesktop, $bundleWeb | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot "web\dist-desktop") -Destination $bundleWeb -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "desktop\main.js") -Destination $bundleDesktop -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "desktop\splash.html") -Destination $bundleDesktop -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "desktop\package.json") -Destination $bundleDesktop -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\manual_up_desktop.ps1") -Destination $bundleScripts -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "scripts\manual_up_desktop.cmd") -Destination $bundleScripts -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\desktop-quickstart.md") -Destination $bundleDocs -Force
$conditionDoc = Get-FirstMatchPath (Join-Path $repoRoot "docs\graduation") "*条件一_满足说明.md"
$conditionChecklist = Get-FirstMatchPath (Join-Path $repoRoot "docs\graduation") "*条件一_验收清单.md"
Copy-Item -LiteralPath $conditionDoc -Destination $bundleDocs -Force
Copy-Item -LiteralPath $conditionChecklist -Destination $bundleDocs -Force

$bundleReadme = @"
# Desktop Runtime Bundle

This folder is the desktop-side delivery bundle for algo-benchmark-platform.

Contents:

- web/dist-desktop: built desktop frontend
- desktop/: desktop runtime entry files
- scripts/manual_up_desktop.cmd
- scripts/manual_up_desktop.ps1
- docs/desktop-quickstart.md
- docs/计算环境_条件一_满足说明.md

Recommended start command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manual_up_desktop.ps1
```

Database mode:

- SQLite by default
- MySQL optional via `-UseMySQL`

Purpose:

- desktop environment demonstration
- desktop delivery evidence for graduation review
"@

Set-Content -LiteralPath (Join-Path $bundleRoot "README.md") -Value $bundleReadme -Encoding UTF8

Write-Host ""
Write-Host "Desktop runtime bundle created:"
Write-Host "  $bundleRoot"
Write-Host "Database mode:"
Write-Host "  $(if ($UseMySQL) { 'MySQL optional enabled by launcher parameter' } else { 'SQLite default' })"
