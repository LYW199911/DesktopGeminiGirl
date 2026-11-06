#!/bin/bash
set -e

# Change directory to the script's directory
cd "$(dirname "$0")"

echo "==================================================="
echo "  Building Ha-Gemi Desktop Pet for macOS (.app)..."
echo "==================================================="

PYTHON_CMD="python3"
if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -d "venv" ] && [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if ! $PYTHON_CMD -m PyInstaller --version >/dev/null 2>&1; then
    echo "[ERROR] 未检测到 pyinstaller，正在安装..."
    $PYTHON_CMD -m pip install pyinstaller
fi

# Run PyInstaller build
$PYTHON_CMD -m PyInstaller HaGemi.spec --noconfirm --distpath dist --workpath build

# If assets wasn't copied to Resources or dist, ensure it's present
if [ -d "dist/Ha-Gemi.app" ]; then
    mkdir -p "dist/Ha-Gemi.app/Contents/Resources/assets"
    cp -R assets/* "dist/Ha-Gemi.app/Contents/Resources/assets/" 2>/dev/null || true
    if [ -f "config.example.json" ]; then
        cp "config.example.json" "dist/Ha-Gemi.app/Contents/Resources/" 2>/dev/null || true
    fi

    echo "==================================================="
    echo "  Packaging Ha-Gemi-macOS.zip..."
    (cd dist && rm -f Ha-Gemi-macOS.zip && zip -r -q -y Ha-Gemi-macOS.zip Ha-Gemi.app)
    echo "[SUCCESS] macOS 打包完成！"
    echo "  - 应用程序: dist/Ha-Gemi.app"
    echo "  - 发布压缩包: dist/Ha-Gemi-macOS.zip"
    echo "  - 若在其他 Mac 上打开提示已损坏，请执行："
    echo "      xattr -cr /Applications/Ha-Gemi.app"
    echo "==================================================="
else
    echo "[SUCCESS] 打包完成于 dist/ 目录！"
fi
