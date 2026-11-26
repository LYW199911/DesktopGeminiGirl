from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QGuiApplication, QFont


class RegionSelectorOverlay(QWidget):
    """
    Fullscreen translucent overlay allowing the user to drag-select a custom
    screen capture rectangle across any monitor (Esc to cancel).
    """
    region_selected = pyqtSignal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Cover the entire virtual desktop across all monitors
        virtual_rect = QRect()
        for screen in QGuiApplication.screens():
            virtual_rect = virtual_rect.united(screen.geometry())
        self.setGeometry(virtual_rect)

        self._origin = QPoint()
        self._current = QPoint()
        self._dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._dragging:
            sel = QRect(self._origin, self._current).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sel, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            pen = QPen(QColor("#ff7aa6"), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(sel)

            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                sel.left(),
                max(20, sel.top() - 8),
                f"{sel.width()} x {sel.height()} (松开鼠标确认)"
            )
        else:
            painter.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "按住鼠标左键拖拽框选要让哈Gemi看到的屏幕区域（按 Esc 取消）"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self._dragging = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            sel = QRect(self._origin, self._current).normalized()
            self.close()
            if sel.width() > 20 and sel.height() > 20:
                global_top_left = self.mapToGlobal(sel.topLeft())
                self.region_selected.emit(
                    global_top_left.x(),
                    global_top_left.y(),
                    sel.width(),
                    sel.height()
                )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
