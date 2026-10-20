# Đọc phôi PDF → một file kết quả (CSV mở bằng Excel). Không ghi Google Sheet, không tải lên Drive.
#   Bấm đúp scripts\doc-phoi.bat → chọn nhiều file PDF (Ctrl+A để chọn hết thư mục) → đợi → file kết quả tự mở.
#   Hoặc kéo thả file PDF / thư mục vào doc-phoi.bat.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Paths)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$py = Join-Path $api ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Chưa có môi trường Python của app ($py)." -ForegroundColor Red; Read-Host "Enter để đóng"; exit 1 }

if (-not $Paths -or $Paths.Count -eq 0) {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = "Chọn phôi PDF (Ctrl+A để chọn hết thư mục)"
    $dlg.Filter = "PDF (*.pdf)|*.pdf"
    $dlg.Multiselect = $true
    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
    $Paths = $dlg.FileNames
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $api
Push-Location $api
try {
    Write-Host "Đọc $($Paths.Count) mục — mỗi lần một file, máy vẫn dùng bình thường..." -ForegroundColor Cyan
    $ErrorActionPreference = "Continue"
    & $py -m wg_core.modules.pdf.batch @Paths --open
} finally {
    Pop-Location
}
Write-Host ""
Read-Host "Xong. Enter để đóng cửa sổ"
