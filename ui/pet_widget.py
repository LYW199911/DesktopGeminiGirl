import os
import json
import math
from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QMenu, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QCursor, QAction, QTransform, QPainter, QPainterPath
from .bubble_widget import SpeechBubble
from .interaction_dialog import InteractionDialog
from config_manager import ConfigManager
from app_paths import ASSETS_DIR

EMOTION_MAP = {
    "confident": "avatar_standing.png",
    "curious": "avatar_bust.png",
    "shocked": "avatar_shocked.png",
    "relieved": "avatar_relieved.png"
}

OUTFIT_LABELS = {
    "confident": "自信傲娇立绘",
    "curious": "呆萌疑惑Q版",
    "shocked": "抱头震惊表情",
    "relieved": "害羞无语擦汗"
}

class DesktopPetWidget(QWidget):
    open_settings = pyqtSignal()
    request_critique = pyqtSignal()
    user_replied = pyqtSignal(str)
    toggle_tts = pyqtSignal()
    toggle_auto = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, avatar_path: str = None, target_height: int = 250, parent=None):
        super().__init__(parent)
        self.config_mgr = ConfigManager()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.target_height = target_height
        if not avatar_path:
            outfits = self.config_mgr.get("outfits", {})
            fn = outfits.get("confident", "avatar_standing.png")
            avatar_path = os.path.join(ASSETS_DIR, fn)

        self.avatar_path = avatar_path
        self.current_filename = os.path.basename(avatar_path)
        self._drag_pos = QPoint()
        self._hover_offset = 0.0
        self._hover_direction = 1.0
        self._facing_left = False
        self._base_pixmap = None
        self._wander_dir = -1
        self._wander_pause_ticks = 0
        self._walk_phase = 0.0
        self._pupil_dx = 0.0
        self._pupil_dy = 0.0
        self._eye_meta = None
        self._base_no_pupils = None
        self._pupil_left = None
        self._pupil_right = None
        self._load_eye_demo_assets()

        # UI: Avatar Label (kept hidden when custom QPainter rendering is active)
        self.avatar_label = QLabel(self)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.hide()
        self._load_avatar(avatar_path)

        # Bubble (Passive Comic Speech Bubble with Typewriter effect)
        self.bubble = SpeechBubble()
        self.bubble.clicked.connect(self.reopen_last_bubble)

        # Interaction Dialog (Interactive reply card)
        self.interaction_dialog = InteractionDialog()
        self.interaction_dialog.user_replied.connect(self.user_replied.emit)

        # Place initially at bottom-right corner of screen
        self._place_at_bottom_right()

        # Subtle hovering animation, eye tracking & wandering timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._step_hover)
        self._anim_timer.start(80)

    def _load_avatar(self, path: str):
        self.avatar_path = path
        self.current_filename = os.path.basename(path)
        if os.path.exists(path):
            pixmap = QPixmap(path)
            scaled = pixmap.scaledToHeight(
                self.target_height,
                Qt.TransformationMode.SmoothTransformation
            )
            if scaled.width() > 220:
                scaled = pixmap.scaledToWidth(
                    220,
                    Qt.TransformationMode.SmoothTransformation
                )

            self._base_pixmap = scaled
            self._apply_facing_pixmap()
            self.avatar_label.resize(scaled.size())
            self.resize(scaled.width() + 12, scaled.height() + 14)
            self.avatar_label.move(6, 7)
        else:
            pet_name = self.config_mgr.get("pet_name", "哈Gemi")
            self.avatar_label.setText(pet_name)
            self.avatar_label.resize(160, 220)
            self.resize(160, 220)

    def update_size(self, new_height: int):
        self.target_height = new_height
        self._load_avatar(self.avatar_path)

    def set_emotion(self, emotion: str):
        """Automatically switch outfit/expression based on critique emotion."""
        cfg_outfits = self.config_mgr.get("outfits", {})
        fallback = EMOTION_MAP.get(emotion.lower(), "avatar_standing.png")
        filename = cfg_outfits.get(emotion.lower(), fallback)
        full_path = os.path.join(ASSETS_DIR, filename)
        if os.path.exists(full_path) and self.current_filename != filename:
            print(f"[DesktopPet] Emotion triggered avatar switch: [{emotion}] -> {filename}", flush=True)
            self._load_avatar(full_path)

    def cycle_next_outfit(self):
        """Cycle to the next outfit/expression."""
        cfg_outfits = self.config_mgr.get("outfits", {})
        filenames = [cfg_outfits.get(k, EMOTION_MAP[k]) for k in ["confident", "curious", "shocked", "relieved"]]
        try:
            curr_idx = filenames.index(self.current_filename)
            next_idx = (curr_idx + 1) % len(filenames)
        except ValueError:
            next_idx = 0
        self.change_outfit(filenames[next_idx])

    def change_outfit(self, filename: str):
        full_path = os.path.join(ASSETS_DIR, filename)
        if os.path.exists(full_path):
            self._load_avatar(full_path)

    def _place_at_bottom_right(self):
        screen_obj = self.screen() or QApplication.primaryScreen()
        geom = screen_obj.availableGeometry() if screen_obj else None
        saved_x = self.config_mgr.get("pet_pos_x", None)
        saved_y = self.config_mgr.get("pet_pos_y", None)

        if saved_x is not None and saved_y is not None and geom:
            try:
                sx, sy = int(saved_x), int(saved_y)
                if geom.x() - 100 <= sx <= geom.x() + geom.width() - 50 and \
                   geom.y() - 100 <= sy <= geom.y() + geom.height() - 50:
                    self.move(sx, sy)
                    print(f"[DesktopPet] Restored saved pet position at ({sx}, {sy})", flush=True)
                    return
            except (ValueError, TypeError):
                pass

        if geom:
            x = geom.x() + geom.width() - self.width() - 80
            y = geom.y() + geom.height() - self.height() - 110
        else:
            x, y = 1400, 700
        self.move(x, y)
        print(f"[DesktopPet] Placed pet at ({x}, {y})", flush=True)

    def _load_eye_demo_assets(self):
        eye_dir = os.path.join(ASSETS_DIR, "eye_demo")
        meta_path = os.path.join(eye_dir, "eye_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    self._eye_meta = json.load(f)
                self._base_no_pupils = QPixmap(os.path.join(eye_dir, "base_no_pupils.png"))
                self._pupil_left = QPixmap(os.path.join(eye_dir, "pupil_left.png"))
                self._pupil_right = QPixmap(os.path.join(eye_dir, "pupil_right.png"))
            except Exception as e:
                print(f"[DesktopPet] Failed to load eye_demo assets: {e}", flush=True)
                self._eye_meta = None

    def _apply_facing_pixmap(self):
        self.update()

    def _step_hover(self):
        self._hover_offset += 0.35 * self._hover_direction
        if abs(self._hover_offset) >= 2.5:
            self._hover_direction *= -1

        # True pupil-only eye tracking (no whole-body jelly wobble)
        if self.config_mgr.get("eye_tracking_enabled", False):
            cursor_pos = QCursor.pos()
            center = self.mapToGlobal(QPoint(self.width() // 2, int(self.height() * 0.25)))
            dx = cursor_pos.x() - center.x()
            dy = cursor_pos.y() - center.y()
            target_dx = max(-4.0, min(4.0, dx / 90.0))
            target_dy = max(-2.5, min(2.5, dy / 90.0))
            self._pupil_dx += (target_dx - self._pupil_dx) * 0.25
            self._pupil_dy += (target_dy - self._pupil_dy) * 0.25
        else:
            self._pupil_dx *= 0.8
            self._pupil_dy *= 0.8

        # Procedural walking gait + non-focus-stealing wandering
        if self.config_mgr.get("wandering_enabled", False) and self._drag_pos.isNull():
            if self._wander_pause_ticks > 0:
                self._wander_pause_ticks -= 1
                self._walk_phase *= 0.85
            else:
                self._walk_phase += 0.32
                screen_obj = self.screen() or QApplication.primaryScreen()
                if screen_obj:
                    geom = screen_obj.availableGeometry()
                    next_x = self.x() + self._wander_dir * 2
                    if next_x <= geom.x() + 10:
                        next_x = geom.x() + 10
                        self._wander_dir = 1
                        self._wander_pause_ticks = 25
                    elif next_x + self.width() >= geom.x() + geom.width() - 10:
                        next_x = geom.x() + geom.width() - self.width() - 10
                        self._wander_dir = -1
                        self._wander_pause_ticks = 25
                    self._facing_left = self._wander_dir < 0
                    self.move(next_x, self.y())
        else:
            self._walk_phase = 0.0

        self.update()

    def paintEvent(self, event):
        if not self._base_pixmap or self._base_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self._base_pixmap.width()
        h = self._base_pixmap.height()
        ox = 6.0
        oy = 7.0 + self._hover_offset

        is_walking = self.config_mgr.get("wandering_enabled", False) and self._drag_pos.isNull() and self._wander_pause_ticks == 0
        if is_walking:
            oy -= abs(math.sin(self._walk_phase)) * 3.0

        use_eye_layers = (
            self.config_mgr.get("eye_tracking_enabled", False)
            and self.current_filename == "avatar_standing.png"
            and self._eye_meta is not None
            and self._base_no_pupils is not None
            and not self._base_no_pupils.isNull()
        )
        draw_pm = self._base_no_pupils.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation) if use_eye_layers else self._base_pixmap

        if self._facing_left:
            painter.translate(ox + w / 2.0, oy + h / 2.0)
            painter.scale(-1.0, 1.0)
            painter.translate(-(ox + w / 2.0), -(oy + h / 2.0))

        if is_walking:
            split_ratio = self._eye_meta.get("leg_split_y_ratio", 0.72) if self._eye_meta else 0.72
            split_y = int(h * split_ratio)
            # Draw upper body with subtle torso sway
            painter.save()
            painter.translate(ox + w / 2.0, oy + split_y)
            painter.rotate(math.sin(self._walk_phase) * 1.5)
            painter.translate(-(ox + w / 2.0), -(oy + split_y))
            painter.drawPixmap(QRectF(ox, oy, w, split_y), draw_pm, QRectF(0, 0, w, split_y))
            painter.restore()

            # Draw left & right legs with alternating swing
            leg_h = h - split_y
            swing = math.sin(self._walk_phase) * 9.0
            for side, angle in ((0, swing), (1, -swing)):
                sx = 0 if side == 0 else w / 2.0
                sw = w / 2.0
                painter.save()
                hip_x = ox + sx + sw / 2.0
                hip_y = oy + split_y
                painter.translate(hip_x, hip_y)
                painter.rotate(angle)
                painter.translate(-hip_x, -hip_y)
                painter.drawPixmap(QRectF(ox + sx, oy + split_y, sw, leg_h), draw_pm, QRectF(sx, split_y, sw, leg_h))
                painter.restore()
        else:
            painter.drawPixmap(int(ox), int(oy), draw_pm)

        # Draw clipped pupil layers on top of sclera
        if use_eye_layers:
            src_w = self._eye_meta["source_w"]
            src_h = self._eye_meta["source_h"]
            sx_scale = w / float(src_w)
            sy_scale = h / float(src_h)
            pdx = -self._pupil_dx if self._facing_left else self._pupil_dx
            pdy = self._pupil_dy

            for eye_key, pupil_pm in (("left_eye", self._pupil_left), ("right_eye", self._pupil_right)):
                if not pupil_pm or pupil_pm.isNull():
                    continue
                em = self._eye_meta[eye_key]
                cx = ox + em["clip_x"] * sx_scale
                cy = oy + em["clip_y"] * sy_scale
                cw = em["clip_w"] * sx_scale
                ch = em["clip_h"] * sy_scale

                painter.save()
                clip_path = QPainterPath()
                clip_path.addEllipse(QRectF(cx, cy, cw, ch))
                painter.setClipPath(clip_path)

                px = ox + em["x"] * sx_scale + pdx
                py = oy + em["y"] * sy_scale + pdy
                pw = em["w"] * sx_scale
                ph = em["h"] * sy_scale
                painter.drawPixmap(QRectF(px, py, pw, ph), pupil_pm, QRectF(0, 0, pupil_pm.width(), pupil_pm.height()))
                painter.restore()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()

    def show_critique(self, text: str, duration_ms: Optional[int] = None):
        self.raise_()
        bw, bh = self.bubble.calculate_size(text)

        # Position bubble nicely above-left of pet based on pre-measured size
        bx = self.x() - bw + 45
        by = self.y() - bh - 6

        # Check screen bounds
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            if bx < geom.x() + 10:
                bx = self.x() + self.width() - 30
            if by < geom.y() + 10:
                by = self.y() + self.height() + 10

        self.bubble.move(bx, by)
        self.bubble.show_text(text, duration_ms=duration_ms)
        self.bubble.raise_()

    def reopen_last_bubble(self):
        """Reopens the last critique in the interaction dialog for chatting."""
        last_text = self.bubble._full_text
        if not last_text or not last_text.strip():
            self.show_critique("刚才还没有锐评记录喵~ 点击我或按 Ctrl+F9 呼叫锐评吧！")
            return

        self.bubble.hide()
        self.interaction_dialog.open_for_critique(last_text, self.pos())

    # Mouse drag & click & wheel events
    def wheelEvent(self, event):
        """Scroll mouse wheel over pet to cycle outfits instantly!"""
        self.cycle_next_outfit()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.cycle_next_outfit()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            if self.bubble.isVisible():
                bw = self.bubble.width()
                bh = self.bubble.height()
                self.bubble.move(new_pos.x() - bw + 45, new_pos.y() - bh - 6)
                self.bubble.raise_()
            if self.interaction_dialog.isVisible():
                dw = self.interaction_dialog.width()
                dh = self.interaction_dialog.height()
                self.interaction_dialog.move(new_pos.x() - dw + 45, new_pos.y() - dh - 10)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.config_mgr.save({
                "pet_pos_x": self.x(),
                "pet_pos_y": self.y()
            })
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.request_critique.emit()
            event.accept()

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(30, 25, 45, 245);
                color: #ffffff;
                border: 1.5px solid #ff4e88;
                border-radius: 10px;
                padding: 6px;
                font-family: "Microsoft YaHei";
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ff4e88;
                color: #ffffff;
            }
        """)

        act_settings = QAction("控制台与设置中心", self)
        act_settings.triggered.connect(self.open_settings.emit)
        menu.addAction(act_settings)

        menu.addSeparator()

        pet_name = self.config_mgr.get("pet_name", "哈Gemi")
        act_critique = QAction(f"呼叫{pet_name}锐评 (Ctrl+F9)", self)
        act_critique.triggered.connect(self.request_critique.emit)
        menu.addAction(act_critique)

        act_reopen = QAction("打开刚才的评论框/吐槽互动", self)
        act_reopen.triggered.connect(self.reopen_last_bubble)
        menu.addAction(act_reopen)

        act_switch = QAction("切换下一个立绘 (滚轮/中键/Ctrl+F11)", self)
        act_switch.triggered.connect(self.cycle_next_outfit)
        menu.addAction(act_switch)

        menu.addSeparator()

        # Outfit submenu
        outfit_menu = menu.addMenu("切换造型/差分")
        outfit_menu.setStyleSheet(menu.styleSheet())

        cfg_outfits = self.config_mgr.get("outfits", {})
        for emo in ["confident", "curious", "shocked", "relieved"]:
            fn = cfg_outfits.get(emo, EMOTION_MAP[emo])
            label = OUTFIT_LABELS.get(emo, emo)
            prefix = "✔ " if self.current_filename == fn else "   "
            action = QAction(f"{prefix}{label}", self)
            action.triggered.connect(lambda checked=False, target_fn=fn: self.change_outfit(target_fn))
            outfit_menu.addAction(action)

        menu.addSeparator()

        act_tts = QAction("切换语音吐槽 (Ctrl+F10)", self)
        act_tts.triggered.connect(self.toggle_tts.emit)
        menu.addAction(act_tts)

        act_auto = QAction("自动感知开关", self)
        act_auto.triggered.connect(self.toggle_auto.emit)
        menu.addAction(act_auto)

        menu.addSeparator()

        act_quit = QAction("退出程序", self)
        act_quit.triggered.connect(self.quit_app.emit)
        menu.addAction(act_quit)

        menu.exec(pos)

    def closeEvent(self, event):
        self.bubble.close()
        self.interaction_dialog.close()
        super().closeEvent(event)
