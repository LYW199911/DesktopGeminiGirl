import os
import sys
import time
import math
import random
import json
from PyQt6.QtWidgets import QWidget, QMenu, QApplication
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont, QCursor, QTransform, QAction

from app_paths import ASSETS_DIR
from config_manager import ConfigManager
from ui.dynamic_bubble_widget import DynamicSpeechBubble
from ui.interaction_dialog import InteractionDialog

DYNAMIC_ACTIONS_DIR = os.path.join(ASSETS_DIR, "dynamic_actions")

ACTION_DEFS = {
    "idle": {"file": "待机呼吸休闲", "loop": True, "title": "待机呼吸"},
    "thinking": {"file": "工作状态-思考冒泡", "loop": True, "title": "思考冒泡"},
    "happy": {"file": "点击回应-开心跃动", "loop": False, "title": "开心跃动"},
    "dangling": {"file": "被鼠标拖拽悬空反馈", "loop": True, "title": "悬空挣扎"},
    "coding": {"file": "写代码", "loop": True, "title": "写代码"},
    "shocked": {"file": "被吓一跳", "loop": False, "title": "被吓一跳"}
}

class FloatingParticle:
    def __init__(self, x, y):
        self.x = x + random.uniform(-18, 18)
        self.y = y + random.uniform(-8, 8)
        self.vx = random.uniform(-1.0, 1.0)
        self.vy = random.uniform(-3.2, -1.6)
        self.alpha = 255.0
        self.size = random.uniform(15, 23)
        self.char = random.choice(["♥", "✨", "🌸", "⭐", "✦"])
        self.color = random.choice([
            QColor(255, 105, 180),
            QColor(255, 182, 193),
            QColor(255, 215, 0),
            QColor(186, 85, 211),
            QColor(147, 112, 219)
        ])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.alpha -= 5.5
        return self.alpha > 0

class DynamicDesktopPetWidget(QWidget):
    open_settings = pyqtSignal()
    request_critique = pyqtSignal()
    user_replied = pyqtSignal(str)
    toggle_tts = pyqtSignal()
    toggle_auto = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_mgr = ConfigManager()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.scale_factor = 0.52
        self.dynamic_fps = int(self.config_mgr.get("dynamic_fps", 15))
        self.playback_speed_multiplier = self.dynamic_fps / 12.0
        self.last_critique_text = ""

        # Action cache
        self.actions = {}
        self._load_actions()

        self.current_action_key = "idle"
        self.current_frame = 0
        self.frame_accumulator = 0.0
        self.last_update_time = time.perf_counter()

        # 60 FPS Physics State
        self.is_dragging = False
        self._drag_pos = QPoint()
        self.last_global_pos = QPoint()
        self.velocity_x = 0.0
        self.tilt_angle = 0.0
        self.target_tilt = 0.0
        self.scale_y_ease = 1.0
        self.scale_x_ease = 1.0
        self.particles = []
        self.time_counter = 0.0

        # Sub-widgets: Compact Bubble & Interaction Dialog
        self.bubble = DynamicSpeechBubble()
        self.bubble.clicked.connect(self.reopen_last_bubble)

        self.interaction_dialog = InteractionDialog()
        self.interaction_dialog.user_replied.connect(self.user_replied.emit)

        # Place initially at bottom-right
        self._apply_size()
        self._place_at_bottom_right()

        # 60 FPS Render & Physics Loop (16ms)
        self.physics_timer = QTimer(self)
        self.physics_timer.timeout.connect(self._step_60fps)
        self.physics_timer.start(16)

    def _load_actions(self):
        for k, info in ACTION_DEFS.items():
            jp = os.path.join(DYNAMIC_ACTIONS_DIR, f"{info['file']}.json")
            wp = os.path.join(DYNAMIC_ACTIONS_DIR, f"{info['file']}.webp")
            if os.path.exists(jp) and os.path.exists(wp):
                with open(jp, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                pix = QPixmap(wp)
                self.actions[k] = {
                    "meta": meta,
                    "pixmap": pix,
                    "frame_w": meta["FrameWidth"],
                    "frame_h": meta["FrameHeight"],
                    "columns": meta["Columns"],
                    "rows": meta["Rows"],
                    "count": meta["FrameCount"],
                    "base_fps": meta.get("SampleFps", 12),
                    "loop": info["loop"],
                    "title": info["title"]
                }
        print(f"[DynamicPet] Loaded {len(self.actions)} dynamic animation action packs.")

    def _apply_size(self):
        act = self.actions.get(self.current_action_key)
        if act:
            w = int(act["frame_w"] * self.scale_factor)
            h = int(act["frame_h"] * self.scale_factor)
            self.resize(w + 30, h + 30)
        else:
            self.resize(240, 240)

    def _place_at_bottom_right(self):
        screen = self.screen() or QApplication.primaryScreen()
        geom = screen.availableGeometry() if screen else None
        if geom:
            x = geom.x() + geom.width() - self.width() - 80
            y = geom.y() + geom.height() - self.height() - 110
        else:
            x, y = 1400, 700
        self.move(x, y)

    def set_action(self, key: str):
        if key in self.actions and self.current_action_key != key:
            self.current_action_key = key
            self.current_frame = 0
            self.frame_accumulator = 0.0
            self._apply_size()
            self.update()

    def set_thinking(self, is_thinking: bool):
        if is_thinking:
            self.set_action("thinking")
        else:
            if self.current_action_key == "thinking":
                self.set_action("idle")

    def set_emotion(self, emotion: str):
        em = emotion.lower()
        if em == "shocked":
            self.set_action("shocked")
        elif em == "curious":
            self.set_action("thinking")
        elif em in ["confident", "relieved"]:
            self.trigger_happy_reaction()
        else:
            self.set_action("idle")

    def cycle_next_outfit(self):
        keys = list(ACTION_DEFS.keys())
        try:
            curr_idx = keys.index(self.current_action_key)
            next_idx = (curr_idx + 1) % len(keys)
        except ValueError:
            next_idx = 0
        target = keys[next_idx]
        self.set_action(target)
        title = ACTION_DEFS[target]["title"]
        self.show_critique(f"已切换动作：【{title}】喵~")

    def update_size(self, new_height: int):
        self.scale_factor = max(0.35, min(0.85, new_height / 380.0))
        self._apply_size()
        self.update()

    def set_dynamic_fps(self, fps: int):
        self.dynamic_fps = max(6, min(36, int(fps)))
        self.playback_speed_multiplier = self.dynamic_fps / 12.0

    def trigger_happy_reaction(self, x=None, y=None):
        if x is None:
            x = self.width() / 2.0
        if y is None:
            y = self.height() / 3.0
        for _ in range(7):
            self.particles.append(FloatingParticle(x, y))
        self.set_action("happy")

    def _calc_bubble_pos(self, bw: int, bh: int) -> tuple[int, int]:
        """Calculates exact bubble position so comic tail tip points directly at the cat ear."""
        # Catgirl's horizontal center in global coordinates
        head_cx = self.x() + int(self.width() * 0.5)
        # Catgirl's head top in global coordinates
        head_top_y = self.y() + int(24 * self.scale_factor)

        # In DynamicSpeechBubble, tail tip is at `bx + bw - 14`
        # We want the tail tip to point at catgirl's left cat ear: `head_cx - 8`
        bx = (head_cx - 8) - (bw - 14)
        # Tail tip touches right above the ear
        by = head_top_y - bh + 14

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            # If overflowing left screen edge, flip bubble to the right of pet
            if bx < geom.x() + 10:
                bx = head_cx + 15
            # If overflowing top screen edge, place below pet
            if by < geom.y() + 10:
                by = self.y() + self.height() - 20
        return bx, by

    def show_critique(self, text: str):
        self.last_critique_text = text
        self.raise_()
        bw, bh = self.bubble.calculate_size(text)
        bx, by = self._calc_bubble_pos(bw, bh)

        self.bubble.move(bx, by)
        self.bubble.show_text(text)
        self.bubble.raise_()

    def reopen_last_bubble(self):
        last_text = getattr(self, "last_critique_text", "") or self.bubble._full_text
        if not last_text or not last_text.strip():
            self.show_critique("刚才还没有锐评记录喵~ 点击我或按 Ctrl+F9 呼叫锐评吧！")
            return
        self.bubble.hide()
        self.interaction_dialog.open_for_critique(last_text, self.pos())

    def _step_60fps(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last_update_time)
        self.last_update_time = now
        self.time_counter += dt

        act = self.actions.get(self.current_action_key)
        if act:
            target_fps = act["base_fps"] * self.playback_speed_multiplier
            frame_duration = 1.0 / max(1.0, target_fps)
            self.frame_accumulator += dt

            while self.frame_accumulator >= frame_duration:
                self.frame_accumulator -= frame_duration
                self.current_frame += 1
                if self.current_frame >= act["count"]:
                    if act["loop"]:
                        self.current_frame = 0
                    else:
                        self.set_action("idle")
                        return

        # 60 FPS Physics (Breathing & Swing)
        if not self.is_dragging:
            breath = math.sin(self.time_counter * 3.5) * 0.018
            self.scale_y_ease = 1.0 + breath
            self.scale_x_ease = 1.0 - breath * 0.6
            self.target_tilt = math.sin(self.time_counter * 1.8) * 1.2
        else:
            self.scale_y_ease = 1.06
            self.scale_x_ease = 0.94
            self.target_tilt = max(-22.0, min(22.0, -self.velocity_x * 0.8))

        self.tilt_angle += (self.target_tilt - self.tilt_angle) * 0.22

        if self.particles:
            self.particles = [p for p in self.particles if p.update()]

        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.last_global_pos = event.globalPosition().toPoint()
            self.velocity_x = 0.0
            self.set_action("dangling")
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.cycle_next_outfit()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            curr_pos = event.globalPosition().toPoint()
            self.velocity_x = (curr_pos.x() - self.last_global_pos.x())
            self.last_global_pos = curr_pos
            self.move(curr_pos - self._drag_pos)

            # Move bubble alongside in real time
            if self.bubble.isVisible():
                bx, by = self._calc_bubble_pos(self.bubble.width(), self.bubble.height())
                self.bubble.move(bx, by)
            if hasattr(self, 'interaction_dialog') and self.interaction_dialog.isVisible():
                dw = self.interaction_dialog.width()
                dh = self.interaction_dialog.height()
                self.interaction_dialog.move(self.x() - dw + 45, self.y() - dh - 10)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.velocity_x = 0.0
            self.set_action("idle")
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.trigger_happy_reaction(event.position().x(), event.position().y())
        event.accept()

    def wheelEvent(self, event):
        self.cycle_next_outfit()
        event.accept()

    def _show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b36;
                color: #e0e0e0;
                border: 1px solid #4a4a5a;
                border-radius: 8px;
                padding: 4px;
                font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ff4e88;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4a4a5a;
                margin: 4px 8px;
            }
        """)

        critique_act = QAction("💬 呼叫锐评 (Ctrl+F9)", self)
        critique_act.triggered.connect(self.request_critique.emit)
        menu.addAction(critique_act)

        act_reopen = QAction("💬 打开刚才的评论框/吐槽互动", self)
        act_reopen.triggered.connect(self.reopen_last_bubble)
        menu.addAction(act_reopen)

        switch_act = QAction("🎭 切换动作/神态", self)
        switch_act.triggered.connect(self.cycle_next_outfit)
        menu.addAction(switch_act)

        menu.addSeparator()

        settings_act = QAction("⚙️ 设置中心", self)
        settings_act.triggered.connect(self.open_settings.emit)
        menu.addAction(settings_act)

        tts_act = QAction("🔊 切换语音开关", self)
        tts_act.triggered.connect(self.toggle_tts.emit)
        menu.addAction(tts_act)

        auto_act = QAction("👁️ 自动感知开关", self)
        auto_act.triggered.connect(self.toggle_auto.emit)
        menu.addAction(auto_act)

        menu.addSeparator()

        quit_act = QAction("❌ 退出程序", self)
        quit_act.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_act)

        menu.exec(global_pos)

    def paintEvent(self, event):
        act = self.actions.get(self.current_action_key)
        if not act or act["pixmap"].isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = self.height() - 15.0

        transform = QTransform()
        transform.translate(cx, cy)
        transform.rotate(self.tilt_angle)
        transform.scale(self.scale_x_ease, self.scale_y_ease)
        transform.translate(-cx, -cy)
        painter.setTransform(transform)

        idx = self.current_frame
        col = idx % act["columns"]
        row = idx // act["columns"]
        src_rect = QRect(
            col * act["frame_w"],
            row * act["frame_h"],
            act["frame_w"],
            act["frame_h"]
        )
        dst_w = int(act["frame_w"] * self.scale_factor)
        dst_h = int(act["frame_h"] * self.scale_factor)
        dst_rect = QRect(15, 15, dst_w, dst_h)
        painter.drawPixmap(dst_rect, act["pixmap"], src_rect)

        painter.resetTransform()

        for p in self.particles:
            color = QColor(p.color)
            color.setAlpha(max(0, min(255, int(p.alpha))))
            font = QFont("Segoe UI Emoji", int(p.size))
            painter.setFont(font)
            painter.setPen(color)
            painter.drawText(int(p.x), int(p.y), p.char)
