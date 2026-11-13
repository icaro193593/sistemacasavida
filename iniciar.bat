@echo off
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
