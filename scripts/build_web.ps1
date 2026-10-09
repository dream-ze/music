# Windows 版 build_web.sh:构建前端静态页到 web\out,由后端同源提供
# 前端改动后执行一次即可,后端不用重启。
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_path.ps1")
Set-Location -Path (Join-Path $PSScriptRoot "..\web")
# Empty means same-origin; an explicit environment override supports split hosting.
if (-not $env:NEXT_PUBLIC_API_BASE) { $env:NEXT_PUBLIC_API_BASE = "/" }
if (-not (Test-Path "node_modules")) {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
npm.cmd run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "built web\out (API base: $env:NEXT_PUBLIC_API_BASE)"
