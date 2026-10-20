﻿# Đọc phôi PDF → một file kết quả .xlsx (sheet KET_QUA + CAN_DUYET, mở bằng Excel). Không ghi Google Sheet, không tải lên Drive, không cần web app
# hay Postgres.
#   Bấm đúp lối tắt "Đọc phôi PDF" (hoặc scripts\doc-phoi.vbs) → chọn nhiều PDF (Ctrl+A để chọn hết thư mục)
#   → cửa sổ nhỏ báo tiến độ, đọc lần lượt từng file → file ket-qua-<ngày-giờ>.xlsx tự mở.
#   Kéo thả PDF / thư mục vào lối tắt cũng được.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Paths)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"
$py = Join-Path $api ".venv\Scripts\python.exe"
$icon = Join-Path $PSScriptRoot "doc-phoi.ico"
if (-not (Test-Path $py)) {
    [System.Windows.Forms.MessageBox]::Show("Không thấy môi trường Python của app:`n$py", "Đọc phôi PDF", "OK", "Error") | Out-Null
    exit 1
}

if (-not $Paths -or $Paths.Count -eq 0) {
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = "Chọn phôi PDF (Ctrl+A để chọn hết thư mục)"
    $dlg.Filter = "PDF (*.pdf)|*.pdf"
    $dlg.Multiselect = $true
    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
    $Paths = $dlg.FileNames
}

# ── progress window ──
$form = New-Object System.Windows.Forms.Form
$form.Text = "Đọc phôi PDF"
$form.Size = New-Object System.Drawing.Size(560, 330)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
if (Test-Path $icon) { $form.Icon = New-Object System.Drawing.Icon($icon) }
$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(14, 12); $label.Size = New-Object System.Drawing.Size(520, 22)
$label.Text = "Chuẩn bị đọc $($Paths.Count) mục — mỗi lần một file, máy vẫn dùng bình thường…"
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(14, 38); $bar.Size = New-Object System.Drawing.Size(516, 20)
$log = New-Object System.Windows.Forms.TextBox
$log.Location = New-Object System.Drawing.Point(14, 66); $log.Size = New-Object System.Drawing.Size(516, 180)
$log.Multiline = $true; $log.ReadOnly = $true; $log.ScrollBars = "Vertical"
$log.Font = New-Object System.Drawing.Font("Consolas", 8.5)
$button = New-Object System.Windows.Forms.Button
$button.Location = New-Object System.Drawing.Point(440, 254); $button.Size = New-Object System.Drawing.Size(90, 28)
$button.Text = "Dừng"
$form.Controls.AddRange(@($label, $bar, $log, $button))

# ── the reader: python, no console window, output read line by line ──
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $py
$quoted = $Paths | ForEach-Object { '"' + $_.TrimEnd('\') + '"' }
$psi.Arguments = "-m wg_core.modules.pdf.batch $($quoted -join ' ') --open"
$psi.WorkingDirectory = $api
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
$psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
$psi.EnvironmentVariables["PYTHONPATH"] = $api
$proc = [System.Diagnostics.Process]::Start($psi)
$script:lineTask = $proc.StandardOutput.ReadLineAsync()
$errTask = $proc.StandardError.ReadToEndAsync()  # read alongside, so a full error pipe never blocks the reader
$script:done = $false
$script:result = ""

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
    while ($script:lineTask -and $script:lineTask.IsCompleted) {
        $line = $script:lineTask.Result
        if ($null -eq $line) { $script:lineTask = $null; break }
        $log.AppendText($line + "`r`n")
        if ($line -match '^\s*(\d+)/(\d+)\s+(\S.*?)\s{2,}') {
            $bar.Maximum = [int]$Matches[2]; $bar.Value = [Math]::Min([int]$Matches[1], $bar.Maximum)
            $label.Text = "Đang đọc $($Matches[1])/$($Matches[2]) — $($Matches[3])"
        }
        if ($line -match '^Kết quả: (.+)$') { $script:result = $Matches[1] }
        $script:lineTask = $proc.StandardOutput.ReadLineAsync()
    }
    if (-not $script:done -and $null -eq $script:lineTask -and $proc.HasExited) {
        $script:done = $true
        $timer.Stop()
        $button.Text = "Đóng"
        if ($proc.ExitCode -eq 0 -and $script:result) {
            $bar.Value = $bar.Maximum
            $label.Text = "Xong — file kết quả đã mở bằng Excel."
        } else {
            $label.Text = "Có lỗi — xem chi tiết bên dưới."
            $tail = ($errTask.Result -split "`n" | Where-Object { $_ -and $_ -notmatch " LOG: " } | Select-Object -Last 8) -join "`r`n"
            $log.AppendText("`r`n" + $tail)
        }
    }
})
$button.Add_Click({
    if (-not $script:done -and -not $proc.HasExited) {
        try { $proc.Kill() } catch {}
        $label.Text = "Đã dừng — các file đã đọc vẫn nằm trong file kết quả."
    }
    $form.Close()
})
$form.Add_FormClosing({ if (-not $proc.HasExited) { try { $proc.Kill() } catch {} } })
$timer.Start()
[void]$form.ShowDialog()
