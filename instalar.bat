@echo off
title Instalador - Sistema Casa Vida
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_sistema.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% NEQ 0 (
    echo.
    echo A instalacao foi interrompida com erro ^(codigo %EXIT_CODE%^).
    pause
)
exit /b %EXIT_CODE%
