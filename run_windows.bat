@echo off
rem ==============================================================================
rem ACLIMAR Assistant - Script de Arranque Local para Windows
rem Invariantes: Bind exclusivo en 127.0.0.1, Cero SMTP, Credenciales en Keyring
rem ==============================================================================

setlocal enabledelayedexpansion
title ACLIMAR Assistant - Servidor Local (127.0.0.1)

echo [INFO] Inicializando entorno ACLIMAR Assistant para Windows...

rem Forzar modo UTF-8 en Python para compatibilidad con caracteres en consola Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem Detectar interprete de Python (entorno virtual .venv preferente)
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXEC=.venv\Scripts\python.exe"
    echo [INFO] Usando entorno virtual detectado en .venv
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
    echo [INFO] Usando entorno virtual detectado en venv
) else (
    set "PYTHON_EXEC=python"
    echo [WARN] No se detecto .venv. Usando python del PATH del sistema.
)

rem Ejecutar pre-chequeos y servidor local
"%PYTHON_EXEC%" src\run_local.py

if errorlevel 1 (
    echo.
    echo [ERROR] El servidor finalizo con codigo de error %errorlevel%.
    pause
    exit /b %errorlevel%
)

endlocal
