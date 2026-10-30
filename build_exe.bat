@echo off
chcp 65001 >nul
echo ===================================================
echo   Building Ha-Gemi Desktop Pet Executable (.exe)
echo ===================================================
cd /d "%~dp0"
python -m PyInstaller HaGemi.spec --noconfirm --distpath dist --workpath build
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)
xcopy /E /I /Y "assets" "dist\Ha-Gemi\assets" >nul
copy /Y "config.json" "dist\Ha-Gemi\config.json" >nul
echo [SUCCESS] Build finished! Executable is at dist\Ha-Gemi\Ha-Gemi.exe
pause
