@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Install %*
if errorlevel 1 (echo Installation failed. & pause & exit /b 1)
pause
