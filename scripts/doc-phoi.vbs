' Doc phoi PDF: runs doc-phoi.ps1 with no console window (the shortcut on the Desktop points here).
' Files / folders dropped on the shortcut are passed on.
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File """ & here & "\doc-phoi.ps1"""
For Each a In WScript.Arguments
  cmd = cmd & " """ & a & """"
Next
CreateObject("WScript.Shell").Run cmd, 0, False
