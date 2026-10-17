# Quản Lí BM — stop the API, worker and web started by start-local.ps1 (only processes of this repository).
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"
$all = Get-CimInstance Win32_Process
$isApp = { param($x) $x.Name -eq "python.exe" -and ($x.CommandLine -like "*uvicorn*app.main*" -or $x.CommandLine -like "*worker.main*") }
# The venv's python.exe is a launcher that starts the real interpreter as a child: stop both.
$launchers = $all | Where-Object { (& $isApp $_) -and $_.ExecutablePath -like "$api*" }
$ids = @($launchers.ProcessId)
$children = $all | Where-Object { (& $isApp $_) -and $ids -contains $_.ParentProcessId }
$nodes = $all | Where-Object { $_.Name -eq "node.exe" -and $_.CommandLine -like "*next*start*-p*3210*" }
$procs = @($children) + @($launchers) + @($nodes) | Where-Object { $_ }
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "Đã dừng $($procs.Count) tiến trình."
