@echo off
setlocal EnableExtensions
title CHUYEN PDF/ANH SACH TOAN SANG WORD MATHTYPE
cd /d "%~dp0"

echo ===============================================================================
echo   CHUYEN PDF SCAN / ANH SACH TOAN - KHTN SANG WORD MATHTYPE
echo ===============================================================================
echo.

REM 1. Kiem tra moi truong ao .venv da co chua
if exist ".venv\Scripts\python.exe" goto CHECK_CONFIG

echo ===============================================================================
echo   PHAT HIEN LAN DAU KHOI CHAY TREN MAY NAY!
echo   Dang tu dong thiet lap moi truong va cai dat cac thu vien can thiet...
echo ===============================================================================
echo.

REM 2. Tim Python tren he thong
set "PY_CMD="

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto FOUND_PYTHON
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto FOUND_PYTHON
)

py --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py"
    goto FOUND_PYTHON
)

REM Khong tim thay Python
echo.
echo ===============================================================================
echo [X] LOI: May tinh nay chua cai dat Python!
echo.
echo Vui long cai dat Python (khuyen dung ban 3.11 hoac 3.12):
echo   1. Tai tai: https://www.python.org/downloads/
echo   2. QUAN TRONG: O buoc dau cai dat, nho tich vao o:
echo      [v] "Add python.exe to PATH"
echo.
echo Hoac ban co the mo PowerShell va chay lenh tu dong cai:
echo   winget install Python.Python.3.12
echo ===============================================================================
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [*] Tim thay Python (%PY_CMD%). Dang tao moi truong ao .venv...
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo.
    echo [X] Khong the tao moi truong ao .venv.
    echo Vui long dam bao ban co quyen ghi vao thu muc nay!
    echo.
    pause
    exit /b 1
)

echo [*] Dang cai dat cac thu vien (PyQt6, OpenCV, Matplotlib, python-docx...)...
echo [*] (Qua trinh nay chi dien ra 1 lan duy nhat, vui long cho 1-2 phut)...
echo.
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [X] Co loi xay ra trong qua trinh cai dat thu vien!
    echo Vui long kiem tra ket noi mang va thu chay lai file .bat nay.
    echo.
    pause
    exit /b 1
)

echo.
echo ===============================================================================
echo   [V] THIET LAP MOI TRUONG THANH CONG! DANG KHOI CHAY PHAN MEM...
echo ===============================================================================
echo.
timeout /t 2 >nul 2>&1

:CHECK_CONFIG
REM Dam bao file cau hinh ton tai
if not exist "config.json" (
    if exist "config.example.json" (
        copy config.example.json config.json >nul 2>&1
    )
)

:LAUNCH
echo [*] Dang khoi dong giao dien nguoi dung...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" app.py
) else (
    start "" ".venv\Scripts\python.exe" app.py
)

exit /b 0
