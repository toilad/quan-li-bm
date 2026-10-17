# Quản Lí BM — start everything on this Windows machine (API :8000, worker, web :3210).
# Usage (PowerShell, from the repository folder):   .\scripts\start-local.ps1
#        rebuild the web app after updating code:    .\scripts\start-local.ps1 -Build
#        stop everything:                            .\scripts\stop-local.ps1
# Logs: apps\api\data-api.log / data-worker.log / apps\web\web.log  (no request URLs, no secrets are written there).
param([switch]$Build)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"
$py = Join-Path $api ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) { throw "Chưa có môi trường Python: cd apps\api; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" }
if (-not (Test-Path (Join-Path $web "node_modules"))) { throw "Chưa cài thư viện web: cd apps\web; npm install" }

& (Join-Path $PSScriptRoot "stop-local.ps1") | Out-Null

if ($Build -or -not (Test-Path (Join-Path $web ".next\BUILD_ID"))) {
    Write-Host "Đang build giao diện..."
    Push-Location $web
    try { npm run build | Out-Null; if ($LASTEXITCODE -ne 0) { throw "Build giao diện lỗi" } } finally { Pop-Location }
}

# API and worker may start together: the database start-up is serialised inside the app.
Start-Process -WindowStyle Hidden -WorkingDirectory $api -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-access-log" `
    -RedirectStandardOutput (Join-Path $api "data-api.log") -RedirectStandardError (Join-Path $api "data-api.err")
Start-Process -WindowStyle Hidden -WorkingDirectory $api -FilePath $py -ArgumentList "-m", "worker.main" `
    -RedirectStandardOutput (Join-Path $api "data-worker.log") -RedirectStandardError (Join-Path $api "data-worker.err")
Start-Process -WindowStyle Hidden -WorkingDirectory $web -FilePath "node" -ArgumentList "node_modules\next\dist\bin\next", "start", "-p", "3210" `
    -RedirectStandardOutput (Join-Path $web "web.log") -RedirectStandardError (Join-Path $web "web.err")

for ($i = 0; $i -lt 60; $i++) {
    try {
        if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2).StatusCode -eq 200 -and
            (Invoke-WebRequest -UseBasicParsing http://localhost:3210/login -TimeoutSec 2).StatusCode -eq 200) {
            Write-Host "Quản Lí BM đang chạy: http://localhost:3210"
            exit 0
        }
    } catch {}
    Start-Sleep 1
}
Write-Host "Chưa lên sau 60 giây — xem apps\api\data-api.err và apps\web\web.err"
exit 1
