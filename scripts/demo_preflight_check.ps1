# Demo preflight: run from REPOSITORY ROOT so .env.local and paths resolve.
# Example:  powershell -ExecutionPolicy Bypass -File .\scripts\demo_preflight_check.ps1
# Adjust -ApiPort if your uvicorn listens on another port.

param(
  [string]$ApiUrl = "http://127.0.0.1:8001/health",
  [int]$ApiPort = 8001,
  [int]$RedisPort = 6379
)

$ErrorActionPreference = "Continue"

function Write-Ok([string]$msg) { Write-Host "[OK]  $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

Write-Host "=== Demo Preflight Check ===" -ForegroundColor Cyan

$allPass = $true

# 1) API 端口
$apiConn = Test-NetConnection -ComputerName "127.0.0.1" -Port $ApiPort -InformationLevel Quiet
if ($apiConn) {
  Write-Ok "API port $ApiPort is reachable"
} else {
  Write-Warn "API port $ApiPort is NOT reachable"
  $allPass = $false
}

# 2) Redis 端口
$redisConn = Test-NetConnection -ComputerName "127.0.0.1" -Port $RedisPort -InformationLevel Quiet
if ($redisConn) {
  Write-Ok "Redis port $RedisPort is reachable"
} else {
  Write-Warn "Redis port $RedisPort is NOT reachable"
  $allPass = $false
}

# 3) lightweight HTTP readiness check (socket only)
if ($apiConn) {
  Write-Ok "API socket is ready (skip HTTP health to avoid hang)"
} else {
  Write-Warn "API socket not ready"
  $allPass = $false
}

# 4) AI local config
$envFile = Join-Path (Get-Location) ".env.local"
if (Test-Path $envFile) {
  Write-Ok ".env.local exists"
  $line = (Get-Content $envFile | Select-String -Pattern "^\\s*ABP_AI_API_KEY\\s*=" | Select-Object -First 1)
  if ($null -eq $line) {
    Write-Warn "ABP_AI_API_KEY not found (AI will use local fallback)"
  } else {
    $raw = ($line.Line -split "=", 2)[1].Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) {
      Write-Warn "ABP_AI_API_KEY is empty (AI will use local fallback)"
    } else {
      Write-Ok "ABP_AI_API_KEY configured"
    }
  }
} else {
  Write-Warn ".env.local not found (AI will use local fallback)"
}

Write-Host ""
if ($allPass) {
  Write-Host "Result: main flow is demo-ready." -ForegroundColor Green
  exit 0
}

Write-Host "Result: blocking warnings found, fix WARN items first." -ForegroundColor Yellow
exit 1

