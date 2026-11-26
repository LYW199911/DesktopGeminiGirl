import math
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush


def draw_listening_mic(painter: QPainter, widget_width: int, phase_time: float = 0.0):
    """Draws a crisp, upright pulsing microphone badge on the top-right of the pet sprite."""
    painter.save()
    painter.resetTransform()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pulse = 0.5 + 0.5 * math.sin(phase_time * 6.0)
    cx = float(max(24, widget_width - 28))
    cy = 24.0

    # Pulsing outer aura ring
    aura_r = 18.5 + pulse * 4.5
    aura_alpha = int(55 + pulse * 95)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(255, 78, 136, aura_alpha)))
    painter.drawEllipse(QRectF(cx - aura_r, cy - aura_r, aura_r * 2.0, aura_r * 2.0))

    # Crisp badge circle
    badge_r = 15.5
    painter.setBrush(QBrush(QColor(35, 26, 56, 235)))
    painter.setPen(QPen(QColor("#ff4e88"), 2.0))
    painter.drawEllipse(QRectF(cx - badge_r, cy - badge_r, badge_r * 2.0, badge_r * 2.0))

    # Vector microphone icon in crisp white
    painter.setPen(QPen(QColor("#ffffff"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(QBrush(QColor("#ffffff")))
    # Mic head capsule
    painter.drawRoundedRect(QRectF(cx - 3.2, cy - 8.5, 6.4, 9.5), 3.2, 3.2)

    # Mic cradle arc (bottom 180 deg)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(QRectF(cx - 5.6, cy - 4.0, 11.2, 8.6), 180 * 16, 180 * 16)
    # Mic stem & base
    painter.drawLine(int(round(cx)), int(round(cy + 4.8)), int(round(cx)), int(round(cy + 8.0)))
    painter.drawLine(int(round(cx - 3.5)), int(round(cy + 8.0)), int(round(cx + 3.5)), int(round(cy + 8.0)))

    # Animated tiny soundwave dot/arc on badge edge
    wave_alpha = int(140 + pulse * 115)
    painter.setPen(QPen(QColor(255, 160, 195, wave_alpha), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawArc(QRectF(cx - 10.5, cy - 7.5, 21.0, 14.0), -30 * 16, 60 * 16)
    painter.drawArc(QRectF(cx - 10.5, cy - 7.5, 21.0, 14.0), 150 * 16, 60 * 16)

    painter.restore()
