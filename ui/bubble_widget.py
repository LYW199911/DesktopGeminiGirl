from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPolygon

class SpeechBubble(QWidget):
    closed = pyqtSignal()

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
        self.title_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #ff4e88; background: transparent; border: none;")
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
        self.label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.label.setStyleSheet("""
            QLabel {
                color: #1f1b2e;
                background: transparent;
                border: none;
                padding-top: 2px;
                padding-bottom: 2px;
            }
        """)
        card_layout.addWidget(self.label)

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

        # Dynamic resizing based on text character count
        length = len(text)
        if length <= 20:
            target_width = 260
        elif length <= 45:
            target_width = 340
        elif length <= 70:
            target_width = 400
        else:
            target_width = 460

        # Reset size constraints before calculating needed dimensions
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)

        # Pre-measure exact height with full text populated
        self.label.setText(text)
        self.card.layout().activate()
        self.layout().activate()
        target_height = self.layout().heightForWidth(target_width)
        if target_height <= 0:
            target_height = self.sizeHint().height()
        target_height += 8  # Extra breathing room cushion so text never clips

        # LOCK exact target dimensions so the window will never collapse during typing
        self.setFixedSize(target_width, target_height)

        # Reset text for typewriter effect
        self.label.setText("")

        self.show()
        self.raise_()

        # Dynamic duration: longer text gets more reading time
        if duration_ms is None:
            # 8s base + 80ms per character
            duration_ms = max(8000, 7000 + length * 80)

        # Start typewriter effect
        self.type_timer.start(28)
        self.hide_timer.stop()
        self.hide_timer.start(duration_ms)

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
            self.update()  # Force repainting layered window buffer
        else:
            self.type_timer.stop()
            self.update()

    def hide_bubble(self):
        self.type_timer.stop()
        self.hide_timer.stop()
        self.hide()
        self.closed.emit()
