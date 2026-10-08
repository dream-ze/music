# Windows 版 build_web.sh:构建前端静态页到 web\out,由后端同源提供
# 前端改动后执行一次即可,后端不用重启。
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..\web")
if (-not $env:NEXT_PUBLIC_API_BASE) {
    # 网页与 API 同源,API 地址就是公网 Funnel 地址
    $env:NEXT_PUBLIC_API_BASE = "https://192.tail3eff52.ts.net"
}
if (-not (Test-Path "node_modules")) { npm ci }
npx next build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "built web\out (API base: $env:NEXT_PUBLIC_API_BASE)"
