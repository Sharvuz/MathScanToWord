@echo off
chcp 65001 >nul
title CHUYỂN PDF/ẢNH SÁCH TOÁN SANG WORD MATHTYPE
cd /d "%~dp0"

echo ===============================================================================
echo   CHUYỂN PDF SCAN / ẢNH SÁCH TOÁN - KHTN SANG WORD MATHTYPE
echo ===============================================================================
echo.
echo   [*] Đang khởi động giao diện người dùng...
echo   [*] Tự động xoay tua 3 Gemini API Key...
echo   [*] Hỗ trợ kéo thả PDF, xem lại và chỉnh khung cắt hình học...
echo.

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" app.py
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        py app.py
    ) else (
        python app.py
    )
)

exit
