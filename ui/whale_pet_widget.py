import os
import json
import math
import random
from typing import Optional
from PyQt6.QtWidgets import QWidget, QMenu, QApplication
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QCursor, QAction, QPainterPath

from app_paths import ASSETS_DIR
from config_manager import ConfigManager


class WhaleLayeredPetWidget(QWidget):
    """
    Coopanion-style layered 2D rig pet widget using whale model.json + tex/ + feat/.
    Supports true clipped iris/pupil eye-tracking, periodic blinking, articulated
    leg/arm/tail walking gait, and non-focus-stealing desktop wandering.
    """
    open_settings = pyqtSignal()
    request_critique = pyqtSignal()
    user_replied = pyqtSignal(str)
    toggle_tts = pyqtSignal()
    toggle_auto = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, target_height: int = 260, parent=None):
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

        self.whale_dir = os.path.join(ASSETS_DIR, "whale_demo")
        with open(os.path.join(self.whale_dir, "model.json"), "r", encoding="utf-8") as f:
            self.model = json.load(f)

        self.units = self.model["units"]
        self.pivots = self.model["pivots"]
        self.feat = self.model["feat"]

        # Load textures & feature sprites
        self.tex_map = {}
        self.parts = []
        skip_parts = {"skirt_sit", "waist_bow_sit_front"}
        for p in sorted(self.model["parts"], key=lambda x: x["z"]):
            if p["id"] in skip_parts:
                continue
            self.parts.append(p)
            tex_name = p["tex"]
            if tex_name not in self.tex_map:
                path = os.path.join(self.whale_dir, "tex", f"{tex_name}.png")
                self.tex_map[tex_name] = QPixmap(path) if os.path.exists(path) else QPixmap()

        self.feat_map = {}
        feat_dir = os.path.join(self.whale_dir, "feat")
        if os.path.isdir(feat_dir):
            for fn in os.listdir(feat_dir):
                if fn.endswith(".png"):
                    self.feat_map[fn[:-4]] = QPixmap(os.path.join(feat_dir, fn))

        self.rig_size = 256.0
        self.scale_factor = max(0.5, target_height / self.rig_size)
        win_side = int(self.rig_size * self.scale_factor) + 20
        self.resize(win_side, win_side)

        # Animation & interaction state
        self._drag_pos = QPoint()
        self._facing_left = False
        self._wander_dir = 1  # whale stands facing right by default
        self._wander_pause_ticks = 0
        self._walk_phase = 0.0
        self._idle_phase = 0.0
        self._iris_dx = 0.0
        self._iris_dy = 0.0
        self._is_blinking = False
        self._blink_timer = 0
        self._next_blink_ticks = random.randint(45, 95)

        self._place_at_bottom_right()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(33)  # ~30 FPS

    def _u(self, x: float) -> float:
        return 128.0 + (x - self.units["X0"]) * self.units["S"]

    def _v(self, y: float) -> float:
        return 256.0 - (self.units["FEET"] - y) * self.units["S"]

    def _feat_rect(self, coords):
        x1, y1, x2, y2 = coords
        s = self.units["S"]
        return QRectF(self._u(x1), self._v(y1), (x2 - x1) * s, (y2 - y1) * s)

    def _place_at_bottom_right(self):
        screen_obj = self.screen() or QApplication.primaryScreen()
        if screen_obj:
            geom = screen_obj.availableGeometry()
            x = geom.x() + geom.width() - self.width() - 40
            y = geom.y() + geom.height() - self.height() - 10
            self.move(x, y)

    def _step(self):
        self._idle_phase += 0.08

        # Blinking state machine
        if self._is_blinking:
            self._blink_timer -= 1
            if self._blink_timer <= 0:
                self._is_blinking = False
                self._next_blink_ticks = random.randint(60, 140)
        else:
            self._next_blink_ticks -= 1
            if self._next_blink_ticks <= 0:
                self._is_blinking = True
                self._blink_timer = 4

        # True pupil-only eye tracking (rig coordinates)
        cursor_pos = QCursor.pos()
        eye_center = self.mapToGlobal(QPoint(int(self.width() * 0.52), int(self.height() * 0.45)))
        dx = cursor_pos.x() - eye_center.x()
        dy = cursor_pos.y() - eye_center.y()
        target_dx = max(-2.8, min(2.8, dx / 110.0))
        target_dy = max(-2.2, min(2.2, dy / 110.0))
        self._iris_dx += (target_dx - self._iris_dx) * 0.28
        self._iris_dy += (target_dy - self._iris_dy) * 0.28

        # Articulated walking along screen bottom (non-focus-stealing)
        if self._drag_pos.isNull():
            if self._wander_pause_ticks > 0:
                self._wander_pause_ticks -= 1
                self._walk_phase *= 0.85
            else:
                self._walk_phase += 0.18
                screen_obj = self.screen() or QApplication.primaryScreen()
                if screen_obj:
                    geom = screen_obj.availableGeometry()
                    next_x = self.x() + self._wander_dir * 2
                    if next_x <= geom.x() + 10:
                        next_x = geom.x() + 10
                        self._wander_dir = 1
                        self._wander_pause_ticks = 60
                    elif next_x + self.width() >= geom.x() + geom.width() - 10:
                        next_x = geom.x() + geom.width() - self.width() - 10
                        self._wander_dir = -1
                        self._wander_pause_ticks = 60
                    self._facing_left = self._wander_dir < 0
                    self.move(next_x, self.y())

        self.update()

    def _draw_rotated_part(self, painter: QPainter, tex_name: str, box, pivot_name: Optional[str], angle_deg: float, dy: float = 0.0):
        pm = self.tex_map.get(tex_name)
        if not pm or pm.isNull():
            return
        bx, by, bw, bh = box
        painter.save()
        if pivot_name and pivot_name in self.pivots and (abs(angle_deg) > 0.01 or abs(dy) > 0.01):
            px, py = self.pivots[pivot_name]
            painter.translate(px, py + dy)
            painter.rotate(angle_deg)
            painter.translate(-px, -py)
        painter.drawPixmap(QRectF(bx, by, bw, bh), pm, QRectF(0, 0, pm.width(), pm.height()))
        painter.restore()

    def _draw_face_features(self, painter: QPainter):
        eyes = self.feat["eyes"]
        pdx = -self._iris_dx if self._facing_left else self._iris_dx
        pdy = self._iris_dy

        for eye_key in ("eyeL", "eyeR"):
            ed = eyes[eye_key]
            if self._is_blinking:
                sleep_pm = self.feat_map.get(f"sleep_{eye_key}")
                if sleep_pm and not sleep_pm.isNull():
                    lash_rect = self._feat_rect(ed["lash"])
                    painter.drawPixmap(lash_rect, sleep_pm, QRectF(0, 0, sleep_pm.width(), sleep_pm.height()))
                continue

            # 1. Eye white (sclera ball)
            ball_rect = self._feat_rect(ed["ball"])
            ball_pm = self.feat_map.get(f"{eye_key}_ball")
            if ball_pm and not ball_pm.isNull():
                painter.drawPixmap(ball_rect, ball_pm, QRectF(0, 0, ball_pm.width(), ball_pm.height()))

            # 2. Clipped Iris/Pupil tracking cursor
            iris_pm = self.feat_map.get(f"{eye_key}_iris")
            if iris_pm and not iris_pm.isNull():
                painter.save()
                clip = QPainterPath()
                clip.addEllipse(ball_rect)
                painter.setClipPath(clip)
                iris_rect = self._feat_rect(ed["iris"]).translated(pdx, pdy)
                painter.drawPixmap(iris_rect, iris_pm, QRectF(0, 0, iris_pm.width(), iris_pm.height()))
                painter.restore()

            # 3. Eye highlight
            hl_pm = self.feat_map.get(f"{eye_key}_hl")
            if hl_pm and not hl_pm.isNull():
                hl_rect = self._feat_rect(ed["hl"]).translated(pdx * 0.4, pdy * 0.4)
                painter.drawPixmap(hl_rect, hl_pm, QRectF(0, 0, hl_pm.width(), hl_pm.height()))

            # 4. Eyelash
            lash_pm = self.feat_map.get(f"{eye_key}_lash")
            if lash_pm and not lash_pm.isNull():
                lash_rect = self._feat_rect(ed["lash"])
                painter.drawPixmap(lash_rect, lash_pm, QRectF(0, 0, lash_pm.width(), lash_pm.height()))

        # Mouth
        mouth_pm = self.feat_map.get("neutral_mouth")
        mouth_coords = self.feat["sprites"].get("neutral_mouth")
        if mouth_pm and not mouth_pm.isNull() and mouth_coords:
            painter.drawPixmap(self._feat_rect(mouth_coords), mouth_pm, QRectF(0, 0, mouth_pm.width(), mouth_pm.height()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.translate(10.0, 10.0)
        painter.scale(self.scale_factor, self.scale_factor)

        if self._facing_left:
            painter.translate(128.0, 0.0)
            painter.scale(-1.0, 1.0)
            painter.translate(-128.0, 0.0)

        is_walking = self._drag_pos.isNull() and self._wander_pause_ticks == 0
        walk_sin = math.sin(self._walk_phase) if is_walking else 0.0
        bob_y = -abs(walk_sin) * 3.5 if is_walking else math.sin(self._idle_phase) * 1.2
        tail_ang = math.sin(self._idle_phase * 1.1) * 5.0 + walk_sin * 4.0
        hair_ang = math.sin(self._idle_phase * 0.9) * 1.5 - walk_sin * 2.5

        features_drawn = False
        for p in self.parts:
            pid = p["id"]
            if not features_drawn and p["z"] > 8.0:
                painter.save()
                painter.translate(0.0, bob_y)
                self._draw_face_features(painter)
                painter.restore()
                features_drawn = True

            ang = 0.0
            piv = None
            dy = bob_y
            if pid == "leg_front":
                piv, ang, dy = "legFront", walk_sin * 18.0, bob_y * 0.4
            elif pid == "leg_back":
                piv, ang, dy = "legBack", -walk_sin * 18.0, bob_y * 0.4
            elif pid == "arm_near":
                piv, ang = "armNear", -walk_sin * 12.0 + math.sin(self._idle_phase) * 2.0
            elif pid in ("arm_far", "arm_far_end_front"):
                piv, ang = "armFar", walk_sin * 12.0 - math.sin(self._idle_phase) * 2.0
            elif pid == "tail":
                piv, ang = "tail", tail_ang
            elif pid in ("hair_back", "hair_back_curl", "hair_front_left", "hair_front_right"):
                piv, ang = "head", hair_ang
            elif pid in ("fin_near", "fin_far"):
                piv = "finNear" if pid == "fin_near" else "finFar"
                ang = math.sin(self._idle_phase * 1.3) * 4.0
            elif pid == "ahoge":
                piv, ang = "ahoge", math.sin(self._idle_phase * 1.5) * 6.0

            self._draw_rotated_part(painter, p["tex"], p["box"], piv, ang, dy=dy)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            act_quit = QAction("退出 Whale Demo", self)
            act_quit.triggered.connect(QApplication.instance().quit)
            menu.addAction(act_quit)
            menu.exec(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = QPoint()
            event.accept()
