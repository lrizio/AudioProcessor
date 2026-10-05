from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget


class Bar(QWidget):
    """A plain horizontal bar (0..1). Deliberately NOT a QProgressBar: its
    setValue() repaints synchronously, and that call was measured blocking
    for up to half a second with the interpreter held -- which freezes the
    audio threads too. This only schedules a repaint with update()."""

    def __init__(self, width: int | None = None, height: int = 12):
        super().__init__()
        self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        self._frac = 0.0
        self._fill = QLinearGradient(0, 0, 0, height)
        self._fill.setColorAt(0, QColor("#4fa9e0"))
        self._fill.setColorAt(1, QColor("#2a6f96"))

    def set(self, frac: float) -> None:
        frac = min(max(frac, 0.0), 1.0)
        if abs(frac - self._frac) * self.width() >= 1.0 or (frac == 0.0) != (self._frac == 0.0):
            self._frac = frac
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor("#060708"))
        p.setBrush(QColor("#0c0d0f"))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 3, 3)
        w = int((self.width() - 2) * self._frac)
        if w > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(self._fill)
            p.drawRoundedRect(1, 1, w, self.height() - 2, 3, 3)
        p.end()


class Meter(Bar):
    """Peak meter, -60..0 dBFS, fast up / slow down."""

    def __init__(self, width: int | None = 120, height: int = 12):
        super().__init__(width=width, height=height)
        self._db = -60.0

    def feed(self, peak: float) -> None:
        db = 20 * math.log10(max(peak, 1e-6))
        self._db = max(db, self._db - 1.5)
        self.set((self._db + 60.0) / 60.0)
