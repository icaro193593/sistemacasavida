@echo off
if /i not "%~1"=="--minimized" if /i not "%~1"=="--no-min" (
    start "Sistema Casa Vida" /min cmd /c ""%~f0" --minimized"
    exit /b
)
title Sistema Casa Vida
cd /d "%~dp0"

echo =========================================================
echo    Iniciando o Sistema Casa Vida...
echo    Aguarde a abertura automatica no navegador.
echo =========================================================

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe run.py
) else (
    python run.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um problema ao iniciar o sistema.
    pause
)
