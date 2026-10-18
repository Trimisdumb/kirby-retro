@echo off
REM Kirby Retro Launcher - Windows
setlocal EnableDelayedExpansion
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

REM --- Trouve Python : "python" (en ignorant l'alias Microsoft Store), puis "py" ---
set "PY_CMD="
for /f "delims=" %%W in ('where python 2^>nul') do (
  if not defined PY_CMD (
    echo %%W | findstr /i "WindowsApps" >nul
    if !errorlevel! neq 0 set "PY_CMD=python"
  )
)
if not defined PY_CMD (
  where py >nul 2>nul
  if !errorlevel! equ 0 set "PY_CMD=py -3"
)
if not defined PY_CMD (
  echo.
  echo [Kirby Retro Launcher] Python 3.10+ est introuvable.
  echo Telecharge-le sur https://www.python.org/downloads/windows/
  echo et coche "Add python.exe to PATH" pendant l'installation.
  echo.
  pause
  exit /b 1
)

!PY_CMD! -m retro_launcher %*
if errorlevel 1 pause
