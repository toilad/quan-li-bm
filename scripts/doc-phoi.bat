@echo off
rem Doc phoi PDF -> file ket qua. Bam dup, hoac keo tha PDF / thu muc vao file nay.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0doc-phoi.ps1" %*
