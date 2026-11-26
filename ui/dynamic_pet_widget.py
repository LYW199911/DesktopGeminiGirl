import os
import sys
from typing import Optional
import time
import math
import random
import json
import gc
import ctypes
from PyQt6.QtWidgets import QWidget, QMenu, QApplication
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont, QCursor, QTransform, QAction, QImageReader

from app_paths import ASSETS_DIR
from config_manager import ConfigManager
from ui.dynamic_bubble_widget import DynamicSpeechBubble
from ui.interaction_dialog import InteractionDialog
from ui.mic_overlay import draw_listening_mic

DYNAMIC_ACTIONS_DIR = os.path.join(ASSETS_DIR, "dynamic_actions")

ACTION_DEFS = {
    "idle": {"file": "待机呼吸休闲", "loop": True, "title": "待机呼吸"},
    "thinking": {"file": "工作状态-思考冒泡", "loop": True, "title": "思考冒泡"},
    "happy": {"file": "点击回应-开心跃动", "loop": False, "title": "开心跃动"},
    "dangling": {"file": "被鼠标拖拽悬空反馈", "loop": True, "title": "悬空挣扎"},
    "coding": {"file": "写代码", "loop": True, "title": "写代码"},
    "shocked": {"file": "被吓一跳", "loop": False, "title": "被吓一跳"},
    "walk": {"file": "漫步走路", "loop": True, "title": "轻快快走"},
    "walk_slow": {"file": "漫步慢走", "loop": True, "title": "悠闲慢走"},
    "jetpack_start": {"file": "喷气背包-起飞准备", "loop": False, "title": "喷气起飞"},
    "jetpack_fly": {"file": "喷气背包-飞行循环", "loop": True, "title": "喷气飞行"},
    "jetpack_end": {"file": "喷气背包-降落收起", "loop": False, "title": "喷气降落"}
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
    voice_input_start = pyqtSignal()
    voice_input_stop = pyqtSignal()
    focus_arrived = pyqtSignal(object)

    def __init__(self, parent=None):
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

        self._gaze_offset_x = 0.0
        self._gaze_offset_y = 0.0
        self._facing_left = False
        self._wander_dir = -1
        self._wander_pause_ticks = random.randint(360, 900)
        self._wander_move_ticks = 0
        self._wander_mode = "walk_slow"
        self._wander_step_acc = 0.0
        self._bubble_mirrored_right = False
        self._nav_state = None  # None, "jetpack_start", "jetpack_fly", "jetpack_end", "walking"
        self._nav_target = None
        self._nav_focus_rect = None
        self._nav_walk_action = "walk_slow"
        self._nav_fx = 0.0
        self._nav_fy = 0.0
        self._is_voice_listening = False
        self._right_long_pressed = False
        self._right_press_timer = QTimer(self)
        self._right_press_timer.setSingleShot(True)
        self._right_press_timer.timeout.connect(self._on_right_long_press)

        target_h = int(self.config_mgr.get("target_height", 250))
        self.scale_factor = max(0.35, min(0.85, target_h / 380.0))
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

        # Idle memory eviction timer (unloads non-idle actions after 8s in idle)
        self.eviction_timer = QTimer(self)
        self.eviction_timer.setSingleShot(True)
        self.eviction_timer.setInterval(8000)
        self.eviction_timer.timeout.connect(self._evict_unused_actions)
        self.eviction_timer.start()

    def _load_actions(self):
        for k, info in ACTION_DEFS.items():
            jp = os.path.join(DYNAMIC_ACTIONS_DIR, f"{info['file']}.json")
            wp = os.path.join(DYNAMIC_ACTIONS_DIR, f"{info['file']}.webp")
            if os.path.exists(jp) and os.path.exists(wp):
                with open(jp, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.actions[k] = {
                    "meta": meta,
                    "webp_path": wp,
                    "pixmap": None,
                    "is_downscaled": False,
                    "frame_w": meta["FrameWidth"],
                    "frame_h": meta["FrameHeight"],
                    "columns": meta["Columns"],
                    "rows": meta["Rows"],
                    "count": meta["FrameCount"],
                    "base_fps": meta.get("SampleFps", 12),
                    "loop": info["loop"],
                    "title": info["title"]
                }
        # Only load the primary 'idle' action at startup (saves ~550 MB RAM immediately)
        self._ensure_action_loaded("idle")
        print(f"[DynamicPet] Lazy-indexed {len(self.actions)} dynamic animation action packs (Idle loaded, on-demand RAM mode active).")

    def _ensure_action_loaded(self, key: str) -> bool:
        act = self.actions.get(key)
        if not act:
            return False
        if act.get("pixmap") is not None and not act["pixmap"].isNull():
            return True

        wp = act.get("webp_path")
        if not wp or not os.path.exists(wp):
            return False

        use_low_memory = self.config_mgr.get("dynamic_low_memory_mode", True)
        if use_low_memory:
            reader = QImageReader(wp)
            orig_sz = reader.size()
            reader.setScaledSize(QSize(orig_sz.width() // 2, orig_sz.height() // 2))
            img = reader.read()
            act["pixmap"] = QPixmap.fromImage(img)
            act["is_downscaled"] = True
        else:
            act["pixmap"] = QPixmap(wp)
            act["is_downscaled"] = False

        return True

    def _evict_unused_actions(self):
        """Unload non-idle action pixmaps to free hundreds of megabytes of RAM."""
        if self.current_action_key != "idle":
            return
        freed = False
        for k, act in self.actions.items():
            if k != "idle" and act.get("pixmap") is not None:
                act["pixmap"] = None
                freed = True
        if freed:
            gc.collect()
            if sys.platform == "win32":
                try:
                    ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
                except Exception:
                    pass

    def reload_textures(self):
        """Reloads active textures when low memory mode or height setting is modified."""
        for act in self.actions.values():
            act["pixmap"] = None
        self._ensure_action_loaded(self.current_action_key)
        self.update()

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
        saved_x = self.config_mgr.get("pet_pos_x", None)
        saved_y = self.config_mgr.get("pet_pos_y", None)

        if saved_x is not None and saved_y is not None and geom:
            try:
                sx, sy = int(saved_x), int(saved_y)
                if geom.x() - 100 <= sx <= geom.x() + geom.width() - 50 and \
                   geom.y() - 100 <= sy <= geom.y() + geom.height() - 50:
                    self.move(sx, sy)
                    return
            except (ValueError, TypeError):
                pass

        if geom:
            x = geom.x() + geom.width() - self.width() - 80
            y = geom.y() + geom.height() - self.height() - 110
        else:
            x, y = 1400, 700
        self.move(x, y)

    def set_action(self, key: str):
        if key in self.actions and self.current_action_key != key:
            self._ensure_action_loaded(key)
            self.current_action_key = key
            self.current_frame = 0
            self.frame_accumulator = 0.0
            self._apply_size()
            self.update()

            if key == "idle":
                self.eviction_timer.start(8000)
            else:
                self.eviction_timer.stop()

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
        """Calculates exact bubble position so comic tail tip points directly at the cat ear, mirroring smoothly near left edge."""
        head_cx = self.x() + int(self.width() * 0.5)
        head_top_y = self.y() + int(24 * self.scale_factor)

        # Left-side placement: right-bottom tail tip at `bx + bw - 14` points at `head_cx - 8`
        bx_left = (head_cx - 8) - (bw - 14)
        # Right-side mirrored placement: left-bottom tail tip at `bx + 14` points at `head_cx + 8`
        bx_right = (head_cx + 8) - 14
        by = head_top_y - bh + 14

        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            # Hysteresis so bubble mirrors to right when near left edge and cleanly returns left when space is sufficient
            if not self._bubble_mirrored_right and bx_left < geom.x() + 10:
                self._bubble_mirrored_right = True
            elif self._bubble_mirrored_right and bx_left >= geom.x() + 45:
                self._bubble_mirrored_right = False

            bx = bx_right if self._bubble_mirrored_right else bx_left
            if bx + bw > geom.x() + geom.width() - 10:
                bx = geom.x() + geom.width() - bw - 10
            if bx < geom.x() + 10:
                bx = geom.x() + 10
            if by < geom.y() + 10:
                by = self.y() + self.height() - 20
        else:
            bx = bx_right if self._bubble_mirrored_right else bx_left

        self.bubble.set_tail_side("left" if self._bubble_mirrored_right else "right")
        return bx, by

    def show_critique(self, text: str, duration_ms: Optional[int] = None):
        self.last_critique_text = text
        self.raise_()
        bw, bh = self.bubble.calculate_size(text)
        bx, by = self._calc_bubble_pos(bw, bh)

        self.bubble.move(bx, by)
        self.bubble.show_text(text, duration_ms=duration_ms)
        self.bubble.raise_()

    def reopen_last_bubble(self):
        last_text = getattr(self, "last_critique_text", "") or self.bubble._full_text
        if not last_text or not last_text.strip():
            self.show_critique("刚才还没有锐评记录喵~ 点击我或按 Ctrl+F9 呼叫锐评吧！")
            return
        self.bubble.hide()
        self.interaction_dialog.open_for_critique(last_text, self.pos())

    def move_to_focus(self, target_x: int, target_y: int, focus_rect=None):
        """Navigates purposefully to (target_x, target_y) via jetpack flight (if Y changes) or walking, then emits focus_arrived."""
        if self.is_dragging:
            return
        dx = target_x - self.x()
        dy = target_y - self.y()
        self._nav_target = (int(target_x), int(target_y))
        self._nav_focus_rect = focus_rect
        self._nav_fx = float(self.x())
        self._nav_fy = float(self.y())
        if abs(dx) > 4:
            self._facing_left = dx < 0

        if abs(dy) >= 140:
            self._nav_state = "jetpack_start"
            self.set_action("jetpack_start")
        elif abs(dx) > 12:
            self._nav_state = "walking"
            self._nav_target = (int(target_x), self.y())
            self._nav_walk_action = "walk" if abs(dx) > 260 else "walk_slow"
            self.set_action(self._nav_walk_action)
        else:
            self._nav_state = None
            if focus_rect is not None:
                self.focus_arrived.emit(focus_rect)

    def _step_60fps(self):
        # Clean facing-direction tracking (no whole-sprite jelly wobble)
        self._gaze_offset_x = 0.0
        self._gaze_offset_y = 0.0
        if self.config_mgr.get("eye_tracking_enabled", False) and not self.config_mgr.get("wandering_enabled", False):
            cursor_pos = QCursor.pos()
            center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 3))
            dx = cursor_pos.x() - center.x()
            if abs(dx) > 100:
                self._facing_left = dx < 0

        # Purposeful focus navigation (jetpack 2D flight or targeted walk)
        legacy_wander = bool(self.config_mgr.get("wandering_enabled", False))
        walk_on = bool(self.config_mgr.get("walk_enabled", legacy_wander))
        fly_on = bool(self.config_mgr.get("jetpack_fly_enabled", legacy_wander))

        if self._nav_state and not self.is_dragging and self._nav_target:
            if (self._nav_state in ("jetpack_start", "jetpack_fly", "jetpack_end") and not fly_on) or (
                self._nav_state == "walking" and not walk_on
            ):
                self._nav_state = None
                self._nav_target = None
                self._nav_focus_rect = None
                self.set_action("idle")
                return
            tx, ty = self._nav_target
            if self._nav_state == "jetpack_fly":
                dx = tx - self._nav_fx
                dy = ty - self._nav_fy
                dist = math.hypot(dx, dy)
                if dist <= 3.5:
                    self.move(tx, ty)
                    self._nav_state = "jetpack_end"
                    self.set_action("jetpack_end")
                else:
                    speed = min(3.4, max(1.2, dist * 0.08))
                    self._nav_fx += (dx / dist) * speed
                    self._nav_fy += (dy / dist) * speed
                    if abs(dx) > 4:
                        self._facing_left = dx < 0
                    self.move(int(round(self._nav_fx)), int(round(self._nav_fy)))
                if self.bubble.isVisible():
                    bx, by = self._calc_bubble_pos(self.bubble.width(), self.bubble.height())
                    self.bubble.move(bx, by)
            elif self._nav_state == "walking":
                dx = tx - self._nav_fx
                if abs(dx) <= 2.5:
                    self.move(tx, self.y())
                    rect = self._nav_focus_rect
                    self._nav_state = None
                    self._nav_target = None
                    self._nav_focus_rect = None
                    self.set_action("idle")
                    self._wander_pause_ticks = random.randint(900, 2100)
                    if rect is not None:
                        self.focus_arrived.emit(rect)
                else:
                    step_speed = 1.5 if self._nav_walk_action == "walk" else 0.55
                    self._nav_fx += step_speed if dx > 0 else -step_speed
                    self._facing_left = dx < 0
                    self.move(int(round(self._nav_fx)), self.y())
                    if self.bubble.isVisible():
                        bx, by = self._calc_bubble_pos(self.bubble.width(), self.bubble.height())
                        self.bubble.move(bx, by)
        # Occasional wandering: mostly standing still (idle), occasionally strolling or flying to a focus spot
        elif (walk_on or fly_on) and not self.is_dragging and self.current_action_key in ("idle", "walk", "walk_slow"):
            if self._wander_pause_ticks > 0:
                self._wander_pause_ticks -= 1
                if self.current_action_key in ("walk", "walk_slow"):
                    self.set_action("idle")
                if self._wander_pause_ticks == 0:
                    screen_obj = self.screen() or QApplication.primaryScreen()
                    if screen_obj:
                        geom = screen_obj.availableGeometry()
                        bottom_y = geom.y() + geom.height() - self.height() - 5
                        # If perched high up and flying is enabled, fly back down to bottom rest area
                        if fly_on and self.y() < bottom_y - 140 and random.random() < 0.65:
                            tx = max(geom.x() + 12, min(geom.x() + geom.width() - self.width() - 12, self.x() + random.randint(-120, 120)))
                            self.move_to_focus(tx, bottom_y, focus_rect=None)
                        else:
                            try:
                                from perception.window_tracker import get_foreground_window_info
                                from perception.focus_navigator import pick_focus_target
                                winfo = get_foreground_window_info()
                                wrect = None if winfo.get("is_self") else winfo.get("rect")
                                use_walk = (not fly_on) or (walk_on and random.random() < 0.65 and self.y() >= bottom_y - 30)
                                tx, ty, _ = pick_focus_target(wrect, geom.x(), geom.y(), geom.width(), geom.height(), self.width(), self.height(), current_y=self.y(), prefer_bottom_walk=use_walk)
                                if not walk_on and abs(ty - self.y()) < 140:
                                    # Only jetpack enabled: pick a vertical jump target
                                    ty = geom.y() + 40 if self.y() > geom.y() + geom.height() // 2 else bottom_y
                                self.move_to_focus(tx, ty, focus_rect=None)
                            except Exception:
                                self._wander_pause_ticks = random.randint(900, 1800)
            else:
                self._wander_pause_ticks = random.randint(900, 2100)
                if self.current_action_key in ("walk", "walk_slow"):
                    self.set_action("idle")
        elif self.current_action_key in ("walk", "walk_slow") and not self._nav_state:
            self.set_action("idle")

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
                        if self.current_action_key == "jetpack_start" and self._nav_state == "jetpack_start":
                            self._nav_state = "jetpack_fly"
                            self.set_action("jetpack_fly")
                            return
                        elif self.current_action_key == "jetpack_end" and self._nav_state == "jetpack_end":
                            rect = self._nav_focus_rect
                            self._nav_state = None
                            self._nav_target = None
                            self._nav_focus_rect = None
                            self.set_action("idle")
                            self._wander_pause_ticks = random.randint(900, 2100)
                            if rect is not None:
                                self.focus_arrived.emit(rect)
                            return
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

    def set_voice_listening(self, active: bool):
        self._is_voice_listening = bool(active)
        self.update()

    def _on_right_long_press(self):
        self._right_long_pressed = True
        self.voice_input_start.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._nav_state = None
            self._nav_target = None
            self._nav_focus_rect = None
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.last_global_pos = event.globalPosition().toPoint()
            self.velocity_x = 0.0
            self.set_action("dangling")
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.cycle_next_outfit()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._right_long_pressed = False
            self._right_press_timer.start(350)
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
            # Save pet desktop coordinates on drag end
            self.config_mgr.save({
                "pet_pos_x": self.x(),
                "pet_pos_y": self.y()
            })
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._right_press_timer.stop()
            if self._right_long_pressed:
                self._right_long_pressed = False
                self.voice_input_stop.emit()
            else:
                self._show_context_menu(event.globalPosition().toPoint())
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
        if not act:
            return
        if not act.get("pixmap") or act["pixmap"].isNull():
            self._ensure_action_loaded(self.current_action_key)
            if not act.get("pixmap") or act["pixmap"].isNull():
                return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = self.height() - 15.0

        transform = QTransform()
        transform.translate(cx + self._gaze_offset_x, cy + self._gaze_offset_y)
        transform.rotate(self.tilt_angle)
        flip_x = -1.0 if self._facing_left else 1.0
        transform.scale(flip_x * self.scale_x_ease, self.scale_y_ease)
        transform.translate(-cx, -cy)
        painter.setTransform(transform)

        idx = self.current_frame
        col = idx % act["columns"]
        row = idx // act["columns"]

        is_ds = act.get("is_downscaled", False)
        fw = act["frame_w"] // 2 if is_ds else act["frame_w"]
        fh = act["frame_h"] // 2 if is_ds else act["frame_h"]

        src_rect = QRect(
            col * fw,
            row * fh,
            fw,
            fh
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

        if self._is_voice_listening:
            draw_listening_mic(painter, self.width(), self.time_counter)
