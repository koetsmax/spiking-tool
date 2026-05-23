@echo off
setlocal
cd /d "%~dp0"

:: Already admin — run the client directly (no pyuac re-launch needed).
net session >nul 2>&1
if %errorlevel% equ 0 goto :run

:: Re-launch this batch as admin. Windows usually allows this more reliably than
:: elevating python.exe directly (which SmartScreen often blocks as a false positive).
echo Requesting administrator privileges...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b

:run
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Create it first: py -m venv .venv
    pause
    exit /b 1
)
".venv\Scripts\python.exe" client.py
if errorlevel 1 pause
