@echo off
chcp 65001 > nul
title WordScan.me - He thong Web So Hoa Toan Sang Word

echo =======================================================================
echo          KHOI DONG HE THONG WEB WORDSAN.ME (MATHSCAN TO WORD)
echo =======================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Khong tim thay moi truong ao .venv. Dang su dung python he thong...
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=.venv\Scripts\python.exe
)

echo Dang khoi dong Web Server tren cong 8000...
echo Ban co the truy cap bang trinh duyet tai: http://localhost:8000
echo Tai khoan Admin ban dau: admin / admin123
echo.
echo Nhan Ctrl + C de dung Web Server.
echo =======================================================================
echo.

%PYTHON_CMD% run_web.py --port 8000

pause
