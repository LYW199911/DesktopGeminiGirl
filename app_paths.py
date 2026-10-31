import os
import sys

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BASE_DIR = APP_DIR
    # Prefer external assets directory if exists, else fallback to _internal
    if os.path.exists(os.path.join(APP_DIR, "assets")):
        ASSETS_DIR = os.path.join(APP_DIR, "assets")
    elif os.path.exists(os.path.join(APP_DIR, "_internal", "assets")):
        ASSETS_DIR = os.path.join(APP_DIR, "_internal", "assets")
    else:
        ASSETS_DIR = os.path.join(APP_DIR, "assets")
        os.makedirs(ASSETS_DIR, exist_ok=True)

    CONFIG_FILE = os.path.join(APP_DIR, "config.json")
    MEMORY_FILE = os.path.join(APP_DIR, "memory.json")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
    MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")

ICON_PATH = os.path.join(ASSETS_DIR, "app_icon.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = os.path.join(ASSETS_DIR, "avatar_default.png")

def get_asset_path(filename: str) -> str:
    return os.path.join(ASSETS_DIR, filename)
