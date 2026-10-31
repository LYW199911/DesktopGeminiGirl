import ctypes
from typing import Optional, Tuple
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QLineEdit, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPolygon

class SpeechBubble(QWidget):
    closed = pyqtSignal()
    user_replied = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._full_text = ""
        self._is_updating = False

        # Outer Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 16)  # Extra bottom space for bubble tail

        # Inner Card (Puffy White Bubble)
        self.card = QFrame(self)
        self.card.setObjectName("BubbleCard")
        self.card.setStyleSheet("""
            QFrame#BubbleCard {
                background-color: #ffffff;
                border: 2.5px solid #2d2645;
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(15, 10, 15, 12)
        card_layout.setSpacing(6)

        # Header: Title + Close Button (×)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 0, 0)

        self.title_label = QLabel("哈Gemi", self.card)
        t_font = QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold)
        t_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
        self.title_label.setFont(t_font)
        self.title_label.setStyleSheet("color: #ff4e88; background-color: #ffffff; border: none;")
        top_bar.addWidget(self.title_label)

        top_bar.addStretch()

        # Cute Round Close Button
        self.close_btn = QPushButton("×", self.card)
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("关闭气泡")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f2edf7;
                color: #6d6682;
                border: 1px solid #dcd5e8;
                border-radius: 11px;
                font-size: 13px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background-color: #ff4e88;
                color: #ffffff;
                border: 1px solid #ff4e88;
            }
            QPushButton:pressed {
                background-color: #e03672;
            }
        """)
        self.close_btn.clicked.connect(self.hide_bubble)
        top_bar.addWidget(self.close_btn)

        card_layout.addLayout(top_bar)

        # Content Label: Crisp Bold Text on White Background
        self.label = QLabel(self.card)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        lbl_font = QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold)
        lbl_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
        self.label.setFont(lbl_font)
        self.label.setStyleSheet("""
            QLabel {
                color: #1f1b2e;
                background-color: #ffffff;
                border: none;
                padding-top: 1px;
                padding-bottom: 1px;
            }
        """)
        card_layout.addWidget(self.label)

        # Interactive Reply Input Bar
        self.reply_bar = QHBoxLayout()
        self.reply_bar.setContentsMargins(0, 4, 0, 0)
        self.reply_bar.setSpacing(6)

        self.input_reply = QLineEdit(self.card)
        self.input_reply.setPlaceholderText("跟哈Gemi吐槽互动...(Enter发送)")
        self.input_reply.setStyleSheet("""
            QLineEdit {
                background-color: #f7f4fa;
                border: 1.5px solid #dcd5e8;
                border-radius: 12px;
                padding: 4px 10px;
                color: #2d2645;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QLineEdit:focus {
                background-color: #ffffff;
                border: 1.5px solid #ff4e88;
            }
        """)
        self.input_reply.returnPressed.connect(self._send_user_reply)
        self.input_reply.textEdited.connect(self._on_user_typing)
        self.input_reply.installEventFilter(self)
        self.reply_bar.addWidget(self.input_reply)

        self.btn_send = QPushButton("发送", self.card)
        self.btn_send.setFixedSize(46, 26)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #ff4e88;
                color: #ffffff;
                border: none;
                border-radius: 13px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff689a;
            }
            QPushButton:pressed {
                background-color: #e03b73;
            }
        """)
        self.btn_send.clicked.connect(self._send_user_reply)
        self.reply_bar.addWidget(self.btn_send)

        card_layout.addLayout(self.reply_bar)

        main_layout.addWidget(self.card)

        # Auto hide timer
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_bubble)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cr = self.card.geometry()
        # Draw comic tail pointing toward bottom right
        tail_start_x = cr.right() - 40
        tail_tip_x = cr.right() - 20
        tail_tip_y = cr.bottom() + 12

        tail_poly = QPolygon([
            QPoint(tail_start_x, cr.bottom() - 2),
            QPoint(tail_start_x + 18, cr.bottom() - 2),
            QPoint(tail_tip_x, tail_tip_y)
        ])

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(tail_poly)

        painter.setPen(QPen(QColor("#2d2645"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(tail_start_x, cr.bottom() - 1, tail_tip_x, tail_tip_y)
        painter.drawLine(tail_tip_x, tail_tip_y, tail_start_x + 18, cr.bottom() - 1)

    def _force_dwm_refresh(self):
        """Forces Windows DWM to invalidate its redirection surface cache and recomposite layered window immediately."""
        try:
            hwnd = int(self.winId())
            # SWP_NOSIZE(0x0001) | SWP_NOMOVE(0x0002) | SWP_NOZORDER(0x0004) | SWP_NOACTIVATE(0x0010) | SWP_FRAMECHANGED(0x0020) | SWP_SHOWWINDOW(0x0040)
            flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020 | 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
            ctypes.windll.user32.UpdateWindow(hwnd)
        except Exception:
            pass

    def _apply_text_and_resize(self, text: str) -> Tuple[int, int]:
        """Immediately sets text, measures height, and applies exact dimensions without height accumulation."""
        self._full_text = text
        length = len(text)
        if length <= 25:
            target_width = 340
        elif length <= 55:
            target_width = 400
        elif length <= 85:
            target_width = 460
        else:
            target_width = 520

        avail_w = target_width - 50
        # Reset constraints on label before measuring so previous size never accumulates
        self.label.setMinimumSize(0, 0)
        self.label.setMaximumSize(16777215, 16777215)
        self.label.setText(text)

        # Precise font bounding rect for text word wrap
        fm = self.label.fontMetrics()
        rect = fm.boundingRect(0, 0, avail_w, 2000, Qt.TextFlag.TextWordWrap, text)
        lbl_h = max(22, rect.height() + 4)
        self.label.setFixedWidth(avail_w)
        self.label.setFixedHeight(lbl_h)

        # Fixed vertical heights:
        # card margins(22) + top_bar(22) + spacing(12) + reply_bar(26) + outer margins(26) = 108
        target_height = lbl_h + 108
        self.setFixedSize(target_width, target_height)
        return target_width, target_height

    def prepare_text(self, text: str) -> Tuple[int, int]:
        """Pre-computes text layout and bubble dimensions before geometry placement."""
        self._is_updating = True
        self.hide_timer.stop()

        w, h = self._apply_text_and_resize(text)

        # Reset reply input line
        self.input_reply.clear()
        self.input_reply.clearFocus()
        self.input_reply.setEnabled(True)
        self.input_reply.setPlaceholderText("跟哈Gemi吐槽互动...(Enter发送)")
        self.btn_send.setEnabled(True)

        return w, h

    def show_text(self, text: str, duration_ms: Optional[int] = None):
        """Displays new critique text immediately, flushes DWM layered cache, and synchronizes with TTS audio."""
        self.prepare_text(text)

        # If already visible, briefly hide to force Qt/DWM to recreate/clear stale layered surfaces
        if self.isVisible():
            self.hide()

        self.show()
        self.raise_()

        # Synchronously repaint child and top-level layered buffers to flush to DWM
        self.card.repaint()
        self.label.repaint()
        self.repaint()
        self._force_dwm_refresh()
        QApplication.processEvents()

        self._is_updating = False

        # Dynamic reading duration (minimum 10s for interaction)
        if duration_ms is None:
            duration_ms = max(10000, 8000 + len(text) * 80)
        self.hide_timer.start(duration_ms)

    def reopen_last(self) -> bool:
        """Reopens the last critique bubble with full text and focused input box."""
        if not self._full_text or not self._full_text.strip():
            return False

        self.prepare_text(self._full_text)

        if self.isVisible():
            self.hide()

        self.show()
        self.raise_()
        self.activateWindow()
        self.input_reply.setFocus()

        self.card.repaint()
        self.label.repaint()
        self.repaint()
        self._force_dwm_refresh()
        QApplication.processEvents()

        self._is_updating = False

        # 30 seconds duration while idle, paused whenever master types
        self.hide_timer.start(30000)
        return True

    def _send_user_reply(self):
        text = self.input_reply.text().strip()
        if not text:
            return
        self.input_reply.clear()
        self.input_reply.setPlaceholderText("哈Gemi正在思考回应中喵...")
        self.input_reply.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.hide_timer.stop()  # Do not auto-hide while waiting for reply!
        self.user_replied.emit(text)

    def _on_user_typing(self):
        # Pause auto-hide so the bubble does not disappear while master is typing!
        self.hide_timer.stop()

    def eventFilter(self, obj, event):
        if obj == self.input_reply:
            if self._is_updating:
                return super().eventFilter(obj, event)
            if event.type() == QEvent.Type.FocusIn:
                # When user focuses input box, pause auto-hide timer
                self.hide_timer.stop()
            elif event.type() == QEvent.Type.FocusOut:
                # When user unfocuses and hasn't typed anything, resume a gentle 10s hide timer
                if self.isVisible() and not self.input_reply.text().strip():
                    self.hide_timer.stop()
                    self.hide_timer.start(10000)
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def hide_bubble(self):
        self.hide_timer.stop()
        self.input_reply.clear()
        self.input_reply.clearFocus()
        self.hide()
        self.closed.emit()
