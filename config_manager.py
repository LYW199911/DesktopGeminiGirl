import os
import sys
import json
import winreg
from typing import Dict, Any, Tuple
from app_paths import BASE_DIR, CONFIG_FILE

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "GeminiDesktopPet_HaGemi"

CYBER_WHALE_CONFIG = os.path.expanduser(r"C:\Users\linyu\.gemini\cyber-whale\ai_config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_provider": "gemini",  # "gemini" or "openai_compatible"
    "api_key": "",
    "custom_api_url": "https://openrouter.ai/api/v1",
    "model": "gemini-3.8-flash",
    "temperature": 0.88,
    "cooldown_seconds": 45,
    "enable_tts": True,
    "tts_voice": "zh-CN-XiaoyiNeural",
    "tts_rate": "+12%",
    "tts_pitch": "+15Hz",
    "auto_mode": True,
    "target_height": 250,
    "comment_on_games": True,
    "comment_on_videos": True,
    "comment_on_work": True,
    "pet_name": "哈Gemi",
    "catchphrases": ["喵~", "喵？！", "哼~", "盯——"],
    "persona_style": "元气毒舌",
    "custom_system_prompt": "",
    "outfits": {
        "confident": "avatar_standing.png",
        "curious": "avatar_bust.png",
        "shocked": "avatar_shocked.png",
        "relieved": "avatar_relieved.png"
    }
}

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> Dict[str, Any]:
        # 1. Fallback / inherit API key from cyber-whale if empty
        inherited_key = ""
        inherited_model = "gemini-3.8-flash"
        if os.path.exists(CYBER_WHALE_CONFIG):
            try:
                with open(CYBER_WHALE_CONFIG, "r", encoding="utf-8") as f:
                    cw = json.load(f)
                    inherited_key = cw.get("api_key", "").strip()
                    inherited_model = cw.get("model", "gemini-3.8-flash").strip()
            except Exception:
                pass

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"[ConfigManager] Error reading config: {e}")

        # If still no api_key, use inherited
        if not self.config.get("api_key") and inherited_key:
            self.config["api_key"] = inherited_key
        if not self.config.get("model") and inherited_model:
            self.config["model"] = inherited_model

        return self.config

    def save(self, new_config: Dict[str, Any] = None):
        if new_config:
            self.config.update(new_config)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print("[ConfigManager] Settings saved to config.json")
        except Exception as e:
            print(f"[ConfigManager] Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    # Windows Startup Management
    def is_autostart_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
        except (FileNotFoundError, OSError):
            return False

    def set_autostart(self, enable: bool) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    if getattr(sys, 'frozen', False):
                        exe_path = f'"{sys.executable}"'
                    else:
                        exe_path = f'"{os.path.abspath(os.path.join(BASE_DIR, "start_pet.bat"))}"'
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
                    print(f"[ConfigManager] Autostart enabled -> {exe_path}")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        print("[ConfigManager] Autostart disabled")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            print(f"[ConfigManager] Error setting autostart: {e}")
            return False
