# Đọc phôi PDF — lối tắt trên Desktop (owner, 2026-10-20: như app cũ, đọc xong ghi thẳng Google Sheet).
#   Bấm đúp lối tắt "Đọc phôi PDF" → app Quản Lí BM tự bật nếu chưa chạy → mở trang PDF.
#   Chọn / kéo thả nhiều PDF vào trang: đọc lần lượt, phôi OK tự ghi Sheet (Drive + cột K), phôi cần duyệt nằm lại
#   trong danh sách, cuối lô hiện tổng kết. Không tạo file kết quả nào trên máy.
Add-Type -AssemblyName System.Windows.Forms
$url = "http://localhost:3210/pdf"

function Test-App {
    try {
        return (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2).StatusCode -eq 200 -and
               (Invoke-WebRequest -UseBasicParsing http://localhost:3210/login -TimeoutSec 2).StatusCode -eq 200
    } catch { return $false }
}

if (-not (Test-App)) {
    $note = New-Object System.Windows.Forms.Form
    $note.Text = "Đọc phôi PDF"; $note.Size = New-Object System.Drawing.Size(380, 110); $note.StartPosition = "CenterScreen"
    $note.FormBorderStyle = "FixedDialog"; $note.ControlBox = $false; $note.TopMost = $true
    $icon = Join-Path $PSScriptRoot "doc-phoi.ico"
    if (Test-Path $icon) { $note.Icon = New-Object System.Drawing.Icon($icon) }
    $l = New-Object System.Windows.Forms.Label
    $l.Text = "Đang bật app Quản Lí BM… (lần đầu có thể mất 1–2 phút)"; $l.AutoSize = $false
    $l.Size = New-Object System.Drawing.Size(340, 40); $l.Location = New-Object System.Drawing.Point(16, 20)
    $note.Controls.Add($l); $note.Show(); [System.Windows.Forms.Application]::DoEvents()
    $p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "`"$(Join-Path $PSScriptRoot 'start-local.ps1')`""
    $p.WaitForExit()
    $note.Close()
    if (-not (Test-App)) {
        [System.Windows.Forms.MessageBox]::Show("Không bật được app. Xem log trong apps\api\data-api.err và apps\web\web.err.",
            "Đọc phôi PDF", "OK", "Error") | Out-Null
        exit 1
    }
}
Start-Process $url
