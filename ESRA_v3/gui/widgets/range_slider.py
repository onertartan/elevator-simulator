"""
gui/widgets/range_slider.py
============================
RangeSlider: dual-handle slider (port of matlab.ui.control.RangeSlider).
TickSlider:  single-handle QSlider with painted tick labels (port of
             matlab.ui.control.Slider with MajorTicks).

Both accept an explicit `major_ticks` list so tick labels match the
MATLAB app exactly (e.g. [3 5 10 15 20 25 30 35 40 45 50]).
Values snap to integers (the MATLAB app snaps to 0:100), and the
range slider additionally snaps to multiples of `step`.
"""
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget, QSlider, QSizePolicy

HANDLE_RADIUS = 7
TRACK_MARGIN = 14


class RangeSlider(QWidget):
    lowChanged = Signal(int)
    highChanged = Signal(int)
    rangeEdited = Signal(int, int)  # on mouse release: (low, high)

    def __init__(self, minimum=0, maximum=100, low=0, high=100,
                 step=1, major_ticks=None, parent=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._low = low
        self._high = high
        self._step = max(1, step)
        self._ticks = major_ticks
        self._active_handle = None
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---- public API -----------------------------------------------------
    def setStep(self, step):
        self._step = max(1, step)

    def setLow(self, value):
        self._low = self._clamp(value)
        self._high = max(self._high, self._low)
        self.update()
        self.lowChanged.emit(self._low)

    def setHigh(self, value):
        self._high = self._clamp(value)
        self._low = min(self._low, self._high)
        self.update()
        self.highChanged.emit(self._high)

    def low(self):
        return self._low

    def high(self):
        return self._high

    # ---- helpers -----------------------------------------------------
    def _clamp(self, value):
        value = round((value - self._min) / self._step) * self._step + self._min
        return max(self._min, min(self._max, int(value)))

    def _track_rect(self):
        return QRect(TRACK_MARGIN, self.height() // 2 - 10,
                     self.width() - 2 * TRACK_MARGIN, 20)

    def _value_to_x(self, value):
        track = self._track_rect()
        if self._max == self._min:
            return track.left()
        ratio = (value - self._min) / (self._max - self._min)
        return int(track.left() + ratio * track.width())

    def _x_to_value(self, x):
        track = self._track_rect()
        ratio = min(1.0, max(0.0, (x - track.left()) / max(1, track.width())))
        return self._clamp(self._min + ratio * (self._max - self._min))

    def _tick_values(self):
        if self._ticks:
            return self._ticks
        span = self._max - self._min
        step = 1 if span <= 10 else (5 if span <= 20 else 10)
        return list(range(self._min, self._max + 1, step))

    # ---- painting -----------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        mid_y = self.height() // 2
        track = self._track_rect()

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#c7c7c7"))
        p.drawRoundedRect(track.left(), mid_y - 2, track.width(), 4, 2, 2)

        x_low = self._value_to_x(self._low)
        x_high = self._value_to_x(self._high)
        p.setBrush(QColor("#8a8a8a"))
        p.drawRoundedRect(x_low, mid_y - 2, max(0, x_high - x_low), 4, 2, 2)

        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QPen(QColor("#555555")))
        for v in self._tick_values():
            x = self._value_to_x(v)
            p.drawLine(x, mid_y + 8, x, mid_y + 12)
            p.drawText(QRect(x - 15, mid_y + 13, 30, 14), Qt.AlignHCenter, str(v))

        for value, active in ((self._low, self._active_handle == 'low'),
                               (self._high, self._active_handle == 'high')):
            x = self._value_to_x(value)
            p.setBrush(QColor("#4a90d9") if active else QColor("#ffffff"))
            p.setPen(QPen(QColor("#555555"), 1.5))
            p.drawEllipse(QPoint(x, mid_y), HANDLE_RADIUS, HANDLE_RADIUS)

    # ---- mouse ----------------------------------------------------------
    def mousePressEvent(self, event):
        x = event.position().x()
        x_low = self._value_to_x(self._low)
        x_high = self._value_to_x(self._high)
        self._active_handle = 'low' if abs(x - x_low) <= abs(x - x_high) else 'high'
        self._drag_to(x)

    def mouseMoveEvent(self, event):
        if self._active_handle:
            self._drag_to(event.position().x())

    def mouseReleaseEvent(self, event):
        if self._active_handle:
            self.rangeEdited.emit(self._low, self._high)
        self._active_handle = None
        self.update()

    def _drag_to(self, x):
        value = self._x_to_value(x)
        if self._active_handle == 'low':
            self._low = min(value, self._high)
            self.lowChanged.emit(self._low)
        else:
            self._high = max(value, self._low)
            self.highChanged.emit(self._high)
        self.update()


class TickSlider(QSlider):
    """Single-handle slider with painted tick labels beneath the groove."""

    def __init__(self, minimum, maximum, value, major_ticks=None, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setRange(minimum, maximum)
        self.setValue(value)
        self._ticks = major_ticks
        self.setMinimumHeight(42)

    def _tick_values(self):
        if self._ticks:
            return self._ticks
        span = self.maximum() - self.minimum()
        step = 1 if span <= 10 else (5 if span <= 20 else 10)
        return list(range(self.minimum(), self.maximum() + 1, step))

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QPen(QColor("#555555")))
        span = max(1, self.maximum() - self.minimum())
        usable_w = self.width() - 2 * TRACK_MARGIN
        for v in self._tick_values():
            ratio = (v - self.minimum()) / span
            x = int(TRACK_MARGIN + ratio * usable_w)
            p.drawText(QRect(x - 15, self.height() - 14, 30, 14),
                       Qt.AlignHCenter, str(v))
