@echo off
setlocal enabledelayedexpansion
title Gemini Desktop Pet - Ha-Gemi
cd /d "%~dp0"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ===================================================
echo   Starting Gemini Desktop Pet (Ha-Gemi)...
echo   Hotkeys:
echo     Ctrl+F1  : Start / stop voice input
echo     Ctrl+F9  : Instant Screen Critique
echo     Ctrl+F10 : Toggle Voice (Mute/Unmute)
echo     Ctrl+F11 : Cycle Avatar / Outfits
echo     Mouse Wheel / Middle Click on Pet to switch outfit!
echo ===================================================

:: 智能检索 Python 解释器 (优先使用项目自带的 .venv 虚拟环境)
set "PY_CMD="

if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    where py >nul 2>nul
    if !errorlevel! equ 0 (
        set "PY_CMD=py -3"
    ) else (
        where python >nul 2>nul
        if !errorlevel! equ 0 (
            set "PY_CMD=python"
        )
    )
)

if "%PY_CMD%"=="" (
    echo.
    echo [ERROR] 未找到可用的 Python 运行环境！
    echo 请确认已安装 Python 3.10+ 并将其添加至系统环境变量 PATH。
    echo.
    pause
    exit /b 9009
)

echo [INFO] 使用环境: %PY_CMD%
%PY_CMD% main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Process exited with code: %ERRORLEVEL%
    pause
)
pause
