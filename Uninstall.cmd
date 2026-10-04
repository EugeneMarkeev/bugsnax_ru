@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows.ps1" -Action Uninstall %*
if errorlevel 1 (echo Restore failed. & pause & exit /b 1)
pause
