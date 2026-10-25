@echo off
chcp 65001 >nul
title ĐÓNG GÓI MATHSCANTO WORD THÀNH BẢN PORTABLE (.EXE)
cd /d "%~dp0"

echo ===============================================================================
echo   ĐÓNG GÓI MATHSCANTO WORD THÀNH BẢN CHẠY TRỰC TIẾP (PORTABLE STANDALONE)
echo ===============================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [X] Chưa có môi trường .venv. Vui lòng chạy file CHAY_TOOL_GIAO_DIEN.bat trước!
    pause
    exit /b 1
)

echo [*] Đang kiểm tra và cài đặt PyInstaller trong môi trường ảo...
.venv\Scripts\python.exe -m pip install pyinstaller

echo.
echo [*] Bắt đầu đóng gói ứng dụng (quá trình này mất khoảng 1-2 phút)...
.venv\Scripts\pyinstaller.exe --name "MathScanToWord" ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "core;core" ^
    --add-data "gui;gui" ^
    --add-data "config.example.json;." ^
    --add-data "README.md;." ^
    app.py

if errorlevel 1 (
    echo.
    echo [X] Đóng gói thất bại!
    pause
    exit /b 1
)

echo [*] Đang hoàn thiện thư mục Portable...
if not exist "dist\MathScanToWord\config.json" (
    copy config.example.json "dist\MathScanToWord\config.json" >nul
)

echo.
echo ===============================================================================
echo   [V] ĐÓNG GÓI THÀNH CÔNG!
echo.
echo   Thư mục Portable nằm tại: dist\MathScanToWord\
echo   Bạn có thể nén thư mục này thành file .zip hoặc copy sang USB mang đi
echo   bất kỳ máy tính nào cũng nhấp đúp chạy được file MathScanToWord.exe ngay lập tức!
echo ===============================================================================
echo.
pause
