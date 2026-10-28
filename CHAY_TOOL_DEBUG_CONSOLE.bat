@echo off
setlocal EnableExtensions
title [DEBUG] MATH SCAN TO WORD - LIVE CONSOLE
cd /d "%~dp0"

echo ===============================================================================
echo   KHOI CHAY TOOL KEM THEO CONSOLE DE THEO DOI LOG VA DEBUG
echo ===============================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [*] Chua thay moi truong .venv, dang goi trinh tu dong thiet lap...
    call CHAY_TOOL_GIAO_DIEN.bat
    if not exist ".venv\Scripts\python.exe" (
        pause
        exit /b 1
    )
)

if not exist "config.json" (
    if exist "config.example.json" (
        copy config.example.json config.json >nul 2>&1
    )
)

echo [*] Dang khoi chay app.py bang .venv\Scripts\python.exe...
echo.
.venv\Scripts\python.exe app.py
echo.
echo ===============================================================================
echo   Phan mem da tat hoac gap su co. Xem chi tiet thong tin o tren.
echo ===============================================================================
pause
