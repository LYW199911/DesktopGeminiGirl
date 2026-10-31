import os
import sys
import io

# Force UTF-8 on Windows
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import re
import threading
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QGuiApplication

from config_manager import ConfigManager
from log_manager import LogManager
from perception.window_tracker import get_foreground_window_info
from perception.screen_capture import capture_screen_jpeg
from perception.hotkey_listener import GlobalHotkeyManager
from brain.gemini_client import GeminiCritiqueEngine
from brain.rate_limiter import CritiqueRateLimiter
from tts.edge_speaker import EdgeSpeaker
from ui.pet_widget import DesktopPetWidget
from ui.tray_icon import DesktopPetTray
from ui.settings_window import SettingsWindow

from app_paths import BASE_DIR, ASSETS_DIR, ICON_PATH

class DesktopPetController(QObject):
    critique_ready = pyqtSignal(str)

    def __init__(self, pet_widget: DesktopPetWidget, tray_icon: DesktopPetTray, settings_win: SettingsWindow):
        super().__init__()
        self.pet = pet_widget
        self.tray = tray_icon
        self.settings_win = settings_win

        self.config_mgr = ConfigManager()
        self.logger = LogManager()

        # Engines
        self.engine = GeminiCritiqueEngine()
        self.rate_limiter = CritiqueRateLimiter(cooldown_seconds=self.config_mgr.get("cooldown_seconds", 45))
        self.speaker = EdgeSpeaker(
            voice=self.config_mgr.get("tts_voice", "zh-CN-XiaoyiNeural"),
            rate=self.config_mgr.get("tts_rate", "+12%"),
            pitch=self.config_mgr.get("tts_pitch", "+15Hz"),
            enabled=self.config_mgr.get("enable_tts", True)
        )

        self.auto_mode = self.config_mgr.get("auto_mode", True)
        self._is_analyzing = False

        # Connect signals
        self.critique_ready.connect(self._on_critique_ready)

        # Pet signals
        self.pet.open_settings.connect(self.show_settings)
        self.pet.request_critique.connect(self.trigger_manual_critique)
        self.pet.user_replied.connect(self.handle_user_reply)
        self.pet.toggle_tts.connect(self.toggle_tts)
        self.pet.toggle_auto.connect(self.toggle_auto)
        self.pet.quit_app.connect(self.quit)

        # Tray signals
        self.tray.open_settings.connect(self.show_settings)
        self.tray.trigger_critique.connect(self.trigger_manual_critique)
        self.tray.reopen_bubble.connect(self.pet.reopen_last_bubble)
        self.tray.cycle_outfit.connect(self.pet.cycle_next_outfit)
        self.tray.toggle_pet_visibility.connect(self.toggle_visibility)
        self.tray.toggle_tts.connect(self.toggle_tts)
        self.tray.quit_requested.connect(self.quit)

        # Settings window signals
        self.settings_win.settings_applied.connect(self.reload_settings)
        self.settings_win.request_manual_critique.connect(self.trigger_manual_critique)

        # Hotkeys
        self.hotkeys = GlobalHotkeyManager(
            on_trigger_critique=self.trigger_manual_critique,
            on_toggle_mute=self.toggle_tts,
            on_switch_outfit=self.pet.cycle_next_outfit
        )
        self.hotkeys.start()

        # Active Window Monitor Timer (runs every 2.5s)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._check_desktop_state)
        self.monitor_timer.start(2500)

        # Startup Log & Greet
        pet_name = self.config_mgr.get("pet_name", "哈Gemi")
        mem_count = len(self.engine.context_memory.history)
        if mem_count > 0:
            greet_msg = f"{pet_name}已就位喵~ 已加载 {mem_count} 条前情记忆，随时按 Ctrl+F9 呼叫锐评吧！"
            self.logger.info(f"{pet_name} 启动就位！(已加载 {mem_count} 条前情记忆) 双击托盘图标或右键桌宠可打开设置中心。")
        else:
            greet_msg = f"{pet_name}已就位！随时按 Ctrl+F9 接受本喵的锐评吧！"
            self.logger.info(f"{pet_name} 启动就位！双击托盘图标或右键桌宠可打开设置中心。")
        QTimer.singleShot(1000, lambda: self.critique_ready.emit(greet_msg))

    def show_settings(self):
        self.settings_win.show()
        self.settings_win.raise_()
        self.settings_win.activateWindow()

    def reload_settings(self):
        """Called when settings are saved in settings_window."""
        self.config_mgr.load()
        cfg = self.config_mgr.config

        self.auto_mode = cfg.get("auto_mode", True)
        self.rate_limiter.cooldown_seconds = float(cfg.get("cooldown_seconds", 45))

        # Update TTS
        self.speaker.enabled = cfg.get("enable_tts", True)
        self.speaker.voice = cfg.get("tts_voice", "zh-CN-XiaoyiNeural")

        # Update Pet size & appearance
        new_height = int(cfg.get("target_height", 250))
        self.pet.update_size(new_height)

        pet_name = cfg.get("pet_name", "哈Gemi")
        self.pet.bubble.title_label.setText(pet_name)
        self.tray.setToolTip(f"Gemini 赛博猫娘 · {pet_name}\n双击打开控制台与设置中心")

        self.logger.info(f"设置已重新加载，当前桌宠: {pet_name}，冷却: {self.rate_limiter.cooldown_seconds}s")

    def _check_desktop_state(self):
        if not self.auto_mode or self._is_analyzing:
            return

        info = get_foreground_window_info()
        # Ignore our own pet window, terminal, launcher
        if info.get("is_self", False):
            return

        scene = info["scene"]
        title = info["title"]
        proc = info["process"]

        if not title:
            return

        # Check user preferences for scenes
        if scene == "game" and not self.config_mgr.get("comment_on_games", True):
            return
        if scene == "video" and not self.config_mgr.get("comment_on_videos", True):
            return
        if scene == "work" and not self.config_mgr.get("comment_on_work", True):
            return

        if self.rate_limiter.should_trigger_auto(scene, title):
            self.logger.scene(f"自动捕获场景: [{scene}] 窗口: {title} ({proc})")
            self._start_critique_task(scene, title, proc, rect=info.get("rect"))

    def handle_user_reply(self, user_comment: str):
        if self._is_analyzing:
            return
        info = get_foreground_window_info()
        scene = info.get("scene", "general")
        title = info.get("title", "")
        proc = info.get("process", "")

        self.logger.info(f"主人在气泡回复互动: \"{user_comment}\"")
        self._start_user_interaction_task(scene, title, proc, user_comment, rect=info.get("rect"))

    def _start_user_interaction_task(self, scene: str, title: str, proc: str, user_comment: str, rect=None):
        self._is_analyzing = True
        def worker():
            try:
                max_w = 1440 if scene == "video" else 1280
                cap = capture_screen_jpeg(max_width=max_w, quality=80, crop_rect=rect)
                image_b64 = cap[1] if cap else None

                text = self.engine.generate_interactive_reply(scene, title, proc, user_comment, image_b64)
                self.critique_ready.emit(text)
            except Exception as e:
                self.logger.error(f"互动回复任务出错: {e}")
            finally:
                self._is_analyzing = False

        threading.Thread(target=worker, daemon=True).start()

    def trigger_manual_critique(self):
        if self._is_analyzing:
            return
        info = get_foreground_window_info()
        if info.get("is_self", False):
            info["scene"] = "general"
            info["rect"] = None

        self.logger.info(f"手动快捷键召唤锐评: {info['title']}")
        self._start_critique_task(info["scene"], info["title"], info["process"], rect=info.get("rect"), force=True)

    def _start_critique_task(self, scene: str, title: str, proc: str, rect=None, force: bool = False):
        self._is_analyzing = True
        if not force:
            self.rate_limiter.record_critique(scene, title)

        def worker():
            t_start = threading.current_thread().name
            try:
                max_w = 1440 if scene == "video" else 1280
                cap = capture_screen_jpeg(max_width=max_w, quality=80, crop_rect=rect)
                image_b64 = cap[1] if cap else None

                # Generate via Gemini
                text = self.engine.generate_critique(scene, title, proc, image_b64)
                self.critique_ready.emit(text)
            except Exception as e:
                self.logger.error(f"分析任务出错: {e}")
            finally:
                self._is_analyzing = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_critique_ready(self, raw_text: str):
        # Parse emotion tag [shocked], [curious], [relieved], [confident]
        emotion = "confident"
        clean_text = raw_text

        m = re.match(r'^\s*\[([a-zA-Z]+)\]\s*(.*)', raw_text, re.DOTALL)
        if m:
            emotion = m.group(1).lower()
            clean_text = m.group(2).strip()

        pet_name = self.config_mgr.get("pet_name", "哈Gemi")
        self.logger.critique(f"[{emotion.upper()}] {clean_text}")

        # 1. Dynamically switch avatar expression based on emotion
        self.pet.set_emotion(emotion)

        # 2. Show bubble and speak
        self.pet.show()
        self.pet.raise_()
        self.pet.show_critique(clean_text)
        self.speaker.speak_async(clean_text)

    def toggle_tts(self):
        status = self.speaker.toggle()
        msg = "语音播报已开启喵~" if status else "语音播报已静音喵！"
        self.critique_ready.emit(msg)
        self.logger.info(msg)

    def toggle_auto(self):
        self.auto_mode = not self.auto_mode
        msg = "自动感知已开启喵！" if self.auto_mode else "自动感知已休眠（按 Ctrl+F9 手动唤醒）！"
        self.critique_ready.emit(msg)
        self.logger.info(msg)

    def toggle_visibility(self):
        if self.pet.isVisible():
            self.pet.hide()
            self.pet.bubble.hide()
        else:
            self.pet.show()

    def quit(self):
        self.logger.info("退出程序")
        self.hotkeys.stop()
        self.pet.close()
        self.settings_win.close()
        QApplication.instance().quit()

def main():
    # Fix fractional DPI scaling rasterization issues on layered transparent windows
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Pet & Tray & Settings
    pet = DesktopPetWidget(target_height=250)
    tray = DesktopPetTray(icon_path=ICON_PATH)
    settings_win = SettingsWindow()

    pet.show()

    controller = DesktopPetController(pet, tray, settings_win)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
