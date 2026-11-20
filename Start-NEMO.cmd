@echo off
setlocal
cd /d "%~dp0src" || exit /b 1
set "nemoPython=%~dp0.venv\Scripts\python.exe"
if not exist "%nemoPython%" set "nemoPython=%~dp0..\Nemo\.venv\Scripts\python.exe"
if not exist "%nemoPython%" (
    echo Open the project README for Python setup instructions.
    pause
    exit /b 1
)
"%nemoPython%" -m nemo.gui
if errorlevel 1 pause
