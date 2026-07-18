"""
gui/widgets/lamp.py
====================
Non-interactive status lamp, equivalent to matlab.ui.control.Lamp.
In the source app the gray/green circles are *indicators* (not radio
buttons): whichever slider the user touched last gets the green lamp.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

GREEN = QColor(0, 204, 0)
GRAY = QColor(166, 166, 166)


class Lamp(QWidget):
    def __init__(self, on=False, diameter=22, parent=None):
        super().__init__(parent)
        self._on = on
        self._d = diameter
        self.setFixedSize(diameter + 4, diameter + 4)

    def set_on(self, on: bool):
        if self._on != on:
            self._on = on
            self.update()

    def is_on(self):
        return self._on

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(GREEN if self._on else GRAY)
        p.setPen(QPen(QColor("#6a6a6a"), 1))
        p.drawEllipse(2, 2, self._d, self._d)


def swap_lamps(triggered: Lamp, other: Lamp):
    """Port of the MATLAB swapLamps helper."""
    triggered.set_on(True)
    other.set_on(False)
