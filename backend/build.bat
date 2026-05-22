@echo off
REM ============================================================
REM  SSHPilot - build SSHPilot.exe in one command (Windows)
REM  Requirements: Python 3.10+ and Node.js 18+ on PATH.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo [1/5] Building frontend (Vite)...
cd ..\frontend
call npm install || goto :error
call npm run build || goto :error
cd ..\backend

echo.
echo [2/5] Copying frontend build into backend\static ...
if exist static rmdir /s /q static
xcopy /e /i /y ..\frontend\dist static >nul || goto :error

echo.
echo [3/5] Creating Python virtual env and installing deps...
if not exist .venv (
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || goto :error
pip install pyinstaller || goto :error

echo.
echo [4/5] Packaging with PyInstaller...
pyinstaller --noconfirm --clean sshpilot.spec || goto :error

echo.
echo [5/5] Done.
echo   Your executable is at:  backend\dist\SSHPilot.exe
echo   Double-click it to launch. Data is stored in sshpilot_data\ next to the exe.
echo.
goto :eof

:error
echo.
echo BUILD FAILED. See the error above.
exit /b 1
