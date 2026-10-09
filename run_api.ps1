# Windows 版 run_api.sh:载入 .env,用 ACE-Step 的 Python 启动后端(网页 + API 同源,端口 8000)
# 用法:  powershell -ExecutionPolicy Bypass -File run_api.ps1 [-Log]
#   -Log  把输出追加到 backend.log(计划任务等无控制台的场景用)
param([switch]$Log, [ValidateRange(1, 65535)][int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
. (Join-Path $PSScriptRoot "scripts\windows_path.ps1")

# 载入 .env:KEY=VALUE,忽略空行和 # 注释,去掉值两端的引号
if (Test-Path ".env") {
    foreach ($raw in Get-Content ".env" -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $parts = $line.Split("=", 2)
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $value, "Process")
    }
}

# ACE-Step 源码目录:默认与本项目同级的 ACE-Step-1.5
if (-not $env:ACESTEP_PROJECT_ROOT) {
    $env:ACESTEP_PROJECT_ROOT = Join-Path (Split-Path $PSScriptRoot -Parent) "ACE-Step-1.5"
}

# Python:ZE_PYTHON > 官方免安装包 python_embedded > ACE-Step 的 .venv > 本项目 .venv
# Conservative Windows default; explicit .env/process choices remain authoritative.
if (-not $env:ACESTEP_LM_MODEL) { $env:ACESTEP_LM_MODEL = "acestep-5Hz-lm-0.6B" }

$candidates = @(
    $env:ZE_PYTHON,
    (Join-Path $env:ACESTEP_PROJECT_ROOT "python_embedded\python.exe"),
    (Join-Path $env:ACESTEP_PROJECT_ROOT ".venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")
)
$python = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $python) {
    Write-Host "Python not found. Set ZE_PYTHON or put ACE-Step-1.5 next to this folder." -ForegroundColor Red
    Write-Host "Tried: $($candidates -join '; ')"
    exit 1
}

$env:PYTHONUTF8 = "1"          # 让 Python 默认用 UTF-8 读写(中文歌词、日志)
foreach ($tool in @("ffmpeg", "ffprobe")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool not found. Install FFmpeg and restart the terminal."
    }
}
Write-Host "python: $python"
Write-Host "ACE-Step: $env:ACESTEP_PROJECT_ROOT"
if ($Log) {
    & $python -m uvicorn server.app:app --host 0.0.0.0 --port $Port *>> (Join-Path $PSScriptRoot "backend.log")
} else {
    & $python -m uvicorn server.app:app --host 0.0.0.0 --port $Port
}
exit $LASTEXITCODE
