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

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Process exited with code: %ERRORLEVEL%
    pause
)
pause
