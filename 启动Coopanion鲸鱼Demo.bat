@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\pythonw.exe" goto USE_VENV_W
if exist ".venv\Scripts\python.exe" goto USE_VENV
start "" python "main_whale_demo.py"
goto END

:USE_VENV_W
start "" ".venv\Scripts\pythonw.exe" "main_whale_demo.py"
goto END

:USE_VENV
start "" ".venv\Scripts\python.exe" "main_whale_demo.py"
goto END

:END
