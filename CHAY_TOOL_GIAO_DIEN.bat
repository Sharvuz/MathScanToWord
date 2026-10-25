@echo off
chcp 65001 >nul
title CHUYỂN PDF/ẢNH SÁCH TOÁN SANG WORD MATHTYPE
cd /d "%~dp0"

echo ===============================================================================
echo   CHUYỂN PDF SCAN / ẢNH SÁCH TOÁN - KHTN SANG WORD MATHTYPE
echo ===============================================================================
echo.

:: 1. Kiểm tra môi trường ảo .venv
if not exist ".venv\Scripts\python.exe" (
    echo ===============================================================================
    echo   PHÁT HIỆN LẦN ĐẦU KHỞI CHẠY TRÊN MÁY NÀY!
    echo   Đang tự động thiết lập môi trường và cài đặt các thư viện cần thiết...
    echo ===============================================================================
    echo.

    :: Tìm Python trên hệ thống (ưu tiên py -3.12, py -3, sau đó python)
    set "PY_CMD="
    py -3 --version >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    ) else (
        python --version >nul 2>nul
        if %errorlevel% equ 0 (
            set "PY_CMD=python"
        ) else (
            py --version >nul 2>nul
            if %errorlevel% equ 0 (
                set "PY_CMD=py"
            )
        )
    )

    if not defined PY_CMD (
        echo.
        echo ===============================================================================
        echo [X] LỖI: Máy tính này chưa cài đặt Python!
        echo.
        echo Vui lòng cài đặt Python (khuyên dùng bản 3.11 hoặc 3.12):
        echo   1. Tải tại: https://www.python.org/downloads/
        echo   2. QUAN TRỌNG: Ở bước đầu cài đặt, nhớ tích vào ô:
        echo      [v] "Add python.exe to PATH"
        echo.
        echo Hoặc bạn có thể mở PowerShell và chạy lệnh tự động cài:
        echo   winget install Python.Python.3.12
        echo ===============================================================================
        echo.
        pause
        exit /b 1
    )

    echo [*] Tìm thấy Python (%PY_CMD%). Đang tạo môi trường ảo .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [X] Không thể tạo môi trường ảo .venv.
        echo Vui lòng đảm bảo bạn có quyền ghi vào thư mục này!
        echo.
        pause
        exit /b 1
    )

    echo [*] Đang tải và cài đặt các thư viện (PyQt6, OpenCV, PyMuPDF, python-docx...)...
    echo [*] (Quá trình này chỉ diễn ra 1 lần duy nhất, vui lòng chờ 1-2 phút)...
    echo.
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [X] Có lỗi xảy ra trong quá trình cài đặt thư viện!
        echo Vui lòng kiểm tra kết nối mạng và thử chạy lại file .bat này.
        echo.
        pause
        exit /b 1
    )

    if not exist "config.json" (
        if exist "config.example.json" (
            echo [*] Tự động tạo file config.json từ file mẫu...
            copy config.example.json config.json >nul
        )
    )

    echo.
    echo ===============================================================================
    echo   [V] THIẾT LẬP MÔI TRƯỜNG THÀNH CÔNG! ĐANG KHỞI CHẠY PHẦN MỀM...
    echo ===============================================================================
    echo.
    timeout /t 2 >nul
)

:: 2. Đảm bảo file cấu hình tồn tại
if not exist "config.json" (
    if exist "config.example.json" (
        copy config.example.json config.json >nul
    )
)

:: 3. Khởi chạy ứng dụng giao diện
echo [*] Đang khởi động giao diện người dùng...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    start "" ".venv\Scripts\python.exe" app.py
)

exit /b 0

