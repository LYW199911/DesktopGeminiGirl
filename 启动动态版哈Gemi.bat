@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\pythonw.exe" goto USE_VENV_W
if exist ".venv\Scripts\python.exe" goto USE_VENV
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" goto USE_LOCAL
start "" python "main_dynamic.py"
goto END

:USE_VENV_W
start "" ".venv\Scripts\pythonw.exe" "main_dynamic.py"
goto END

:USE_VENV
start "" ".venv\Scripts\python.exe" "main_dynamic.py"
goto END

:USE_LOCAL
start "" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "main_dynamic.py"
goto END

:END
