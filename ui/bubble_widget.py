from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QLineEdit
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPolygon

class SpeechBubble(QWidget):
    closed = pyqtSignal()
    user_replied = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.ToolTip
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._full_text = ""
        self._current_index = 0

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
        card_layout.setContentsMargins(15, 10, 15, 14)
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

        # Content Label: Crisp Black Bold Text on White Background
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

        # Typewriter timer
        self.type_timer = QTimer(self)
        self.type_timer.timeout.connect(self._type_next_char)

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

    def show_text(self, text: str, duration_ms: Optional[int] = None):
        self._full_text = text
        self._current_index = 0

        # Enable input line for chatter
        self.input_reply.setEnabled(True)
        self.input_reply.setPlaceholderText("跟哈Gemi吐槽互动...(Enter发送)")
        self.btn_send.setEnabled(True)

        # Dynamic resizing based on text character count (accommodating input row)
        length = len(text)
        if length <= 20:
            target_width = 330
        elif length <= 45:
            target_width = 380
        elif length <= 70:
            target_width = 430
        else:
            target_width = 480

        # Calculate exact text bounding rect using font metrics to prevent any vertical squishing/clipping
        fm = self.label.fontMetrics()
        available_text_w = max(240, target_width - 50)
        text_rect = fm.boundingRect(0, 0, available_text_w, 2000, Qt.TextFlag.TextWordWrap, text)
        needed_text_h = max(24, text_rect.height() + 8)
        self.label.setMinimumHeight(needed_text_h)

        # Full bubble height: outer margins(26) + card margins(24) + top_bar(22) + spacing(12) + reply_bar(30) + needed_text_h + tail cushion(8)
        target_height = max(140, 26 + 24 + 22 + 12 + 30 + needed_text_h + 8)

        # LOCK exact dimensions so window never collapses or flickers during typing
        self.setFixedSize(target_width, target_height)

        # Reset text for typewriter effect
        self.label.setText("")

        self.show()
        self.raise_()

        # Dynamic duration: longer text gets more reading time (minimum 10s for interaction)
        if duration_ms is None:
            duration_ms = max(10000, 8000 + length * 80)

        # Start typewriter effect
        self.type_timer.start(25)
        self.hide_timer.stop()
        self.hide_timer.start(duration_ms)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _type_next_char(self):
        if self._current_index < len(self._full_text):
            self._current_index += 1
            self.label.setText(self._full_text[:self._current_index])
            self.label.repaint()
        else:
            self.type_timer.stop()
            self.label.repaint()

    def hide_bubble(self):
        self.type_timer.stop()
        self.hide_timer.stop()
        self.hide()
        self.closed.emit()
