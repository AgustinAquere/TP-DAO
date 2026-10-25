@echo off
rem ==========================================================================
rem  VetRed - doble clic para iniciar la aplicacion.
rem  La primera vez crea el entorno virtual (.venv) e instala las dependencias;
rem  las veces siguientes solo reinstala si requirements.txt cambio.
rem  Acepta los mismos argumentos que main.py (por ejemplo: --web).
rem ==========================================================================
setlocal
cd /d "%~dp0"
title VetRed

set "VENV_PY=.venv\Scripts\python.exe"
if exist "%VENV_PY%" goto dependencias

echo Preparando el entorno por primera vez...
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON (where python >nul 2>&1 && set "PYTHON=python")
if not defined PYTHON goto sin_python
%PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1 || goto sin_python
%PYTHON% -m venv .venv || goto error

:dependencias
fc /b requirements.txt .venv\requisitos-instalados.txt >nul 2>&1
if not errorlevel 1 goto iniciar
echo Instalando dependencias (requiere internet, puede tardar unos minutos)...
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt || goto error
copy /y requirements.txt .venv\requisitos-instalados.txt >nul

:iniciar
echo Iniciando VetRed...
start "" ".venv\Scripts\pythonw.exe" main.py %*
exit /b 0

:sin_python
echo.
echo No se pudo encontrar Python 3.11 o superior.
echo Instalelo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH"
echo y vuelva a ejecutar este archivo.
pause
exit /b 1

:error
echo.
echo No se pudo preparar el entorno. Revise los mensajes anteriores.
pause
exit /b 1
