"""
gui/sprites.py
===============
Sprite factory for the traffic-flow animation. Elevator cabins and
waiting-person silhouettes are drawn programmatically with QPainter
(no binary assets needed) and returned as RGBA numpy arrays ready for
pyqtgraph ImageItems. Everything is cached per (kind, colour, state).

Custom artwork: drop PNGs into gui/assets/ to override the generated
sprites - `cabin_closed.png`, `cabin_open.png`, `person.png`. They are
used as-is (car identity is still shown by the coloured roof stripe
frame that flow_view draws around the cell).

All draw sizes are in a fixed pixel grid (SPRITE_PX); flow_view scales
them into 1x1 data cells via ImageItem.setRect, so they stay crisp at
any window size.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen,
                           QBrush, QLinearGradient)

SPRITE_PX = 128          # master raster size (square)
PERSON_ASPECT = 0.62     # person sprites are narrower than tall

_ASSET_DIR = Path(__file__).resolve().parent / "assets"
_cache: Dict[Tuple, np.ndarray] = {}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def cabin_sprite(car_color: QColor, doors_open: bool) -> np.ndarray:
    """Elevator cabin, roof stripe in the car's colour; doors open/closed."""
    key = ("cabin", car_color.name(), doors_open)
    if key not in _cache:
        asset = _load_asset("cabin_open" if doors_open else "cabin_closed")
        _cache[key] = (_image_to_rgba(asset) if asset is not None
                       else _draw_cabin(car_color, doors_open))
    return _cache[key]


def person_sprite(color: QColor) -> np.ndarray:
    """Standing person silhouette tinted in `color`."""
    key = ("person", color.name())
    if key not in _cache:
        asset = _load_asset("person")
        _cache[key] = (_image_to_rgba(asset) if asset is not None
                       else _draw_person(color))
    return _cache[key]


def clear_cache() -> None:
    _cache.clear()


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------
def _new_canvas(w: int, h: int) -> Tuple[QImage, QPainter]:
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    return img, painter


def _draw_cabin(car_color: QColor, doors_open: bool) -> np.ndarray:
    s = SPRITE_PX
    img, p = _new_canvas(s, s)

    shell = QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.92)
    inner = QRectF(s * 0.14, s * 0.24, s * 0.72, s * 0.66)

    # outer shell with a light metallic gradient
    grad = QLinearGradient(shell.topLeft(), shell.bottomRight())
    grad.setColorAt(0.0, QColor("#e8ecef"))
    grad.setColorAt(1.0, QColor("#c6cdd4"))
    p.setPen(QPen(QColor("#4a5158"), s * 0.02))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(shell, s * 0.06, s * 0.06)

    # roof stripe in the car's colour (identity)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(car_color))
    p.drawRoundedRect(QRectF(s * 0.04, s * 0.04, s * 0.92, s * 0.13),
                      s * 0.05, s * 0.05)

    # floor-indicator lamp on the roof stripe
    p.setBrush(QBrush(QColor("#fff3b0")))
    p.setPen(QPen(QColor("#8a7a20"), s * 0.008))
    p.drawEllipse(QPointF(s * 0.5, s * 0.105), s * 0.028, s * 0.028)

    # door frame
    p.setPen(QPen(QColor("#5c646c"), s * 0.015))
    p.setBrush(QBrush(QColor("#8f979f")))
    p.drawRect(inner)

    if doors_open:
        # interior: back wall, floor line, warm ceiling light
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#70777f")))
        p.drawRect(inner.adjusted(s * 0.015, s * 0.015, -s * 0.015, -s * 0.015))
        p.setBrush(QBrush(QColor("#5b626a")))
        p.drawRect(QRectF(inner.left() + s * 0.015, inner.bottom() - s * 0.10,
                          inner.width() - s * 0.03, s * 0.085))
        p.setBrush(QBrush(QColor("#ffe9a8")))
        p.drawRect(QRectF(inner.left() + s * 0.08, inner.top() + s * 0.02,
                          inner.width() - s * 0.16, s * 0.03))
        # door panels parked at the sides
        p.setPen(QPen(QColor("#4a5158"), s * 0.01))
        p.setBrush(QBrush(QColor("#c3cad1")))
        pw = inner.width() * 0.14
        p.drawRect(QRectF(inner.left(), inner.top(), pw, inner.height()))
        p.drawRect(QRectF(inner.right() - pw, inner.top(), pw, inner.height()))
    else:
        # closed panels meeting at a centre seam
        p.setPen(QPen(QColor("#4a5158"), s * 0.01))
        p.setBrush(QBrush(QColor("#cdd4da")))
        half = inner.width() / 2
        p.drawRect(QRectF(inner.left(), inner.top(), half, inner.height()))
        p.drawRect(QRectF(inner.left() + half, inner.top(), half,
                          inner.height()))
        p.setPen(QPen(QColor("#3a4046"), s * 0.012))
        p.drawLine(QPointF(inner.center().x(), inner.top()),
                   QPointF(inner.center().x(), inner.bottom()))
        # small windows on the panels
        p.setPen(QPen(QColor("#5c646c"), s * 0.008))
        p.setBrush(QBrush(QColor("#aeb6bd")))
        for cx in (inner.center().x() - half / 2, inner.center().x() + half / 2):
            p.drawRoundedRect(QRectF(cx - s * 0.045, inner.top() + s * 0.06,
                                     s * 0.09, s * 0.16), s * 0.02, s * 0.02)

    p.end()
    return _image_to_rgba(img)


def _draw_person(color: QColor) -> np.ndarray:
    w = int(SPRITE_PX * PERSON_ASPECT)
    h = SPRITE_PX
    img, p = _new_canvas(w, h)
    outline = QColor(color).darker(160)
    p.setPen(QPen(outline, h * 0.02))
    p.setBrush(QBrush(color))

    # head
    p.drawEllipse(QPointF(w * 0.5, h * 0.16), w * 0.20, h * 0.115)

    # torso + arms as one rounded path
    body = QPainterPath()
    body.moveTo(w * 0.50, h * 0.27)
    body.cubicTo(w * 0.18, h * 0.28, w * 0.12, h * 0.42, w * 0.16, h * 0.60)
    body.lineTo(w * 0.30, h * 0.60)
    body.lineTo(w * 0.30, h * 0.55)
    body.cubicTo(w * 0.30, h * 0.66, w * 0.70, h * 0.66, w * 0.70, h * 0.55)
    body.lineTo(w * 0.70, h * 0.60)
    body.lineTo(w * 0.84, h * 0.60)
    body.cubicTo(w * 0.88, h * 0.42, w * 0.82, h * 0.28, w * 0.50, h * 0.27)
    body.closeSubpath()
    p.drawPath(body)

    # legs
    p.drawRoundedRect(QRectF(w * 0.32, h * 0.60, w * 0.14, h * 0.34),
                      w * 0.05, w * 0.05)
    p.drawRoundedRect(QRectF(w * 0.54, h * 0.60, w * 0.14, h * 0.34),
                      w * 0.05, w * 0.05)
    p.end()
    return _image_to_rgba(img)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load_asset(name: str) -> Optional[QImage]:
    path = _ASSET_DIR / f"{name}.png"
    if path.exists():
        img = QImage(str(path))
        if not img.isNull():
            return img
    return None


def _image_to_rgba(img: QImage) -> np.ndarray:
    """QImage -> (h, w, 4) uint8 RGBA array (handles scanline padding)."""
    img = img.convertToFormat(QImage.Format_RGBA8888)
    h, w, stride = img.height(), img.width(), img.bytesPerLine()
    buf = np.frombuffer(img.constBits(), np.uint8, count=h * stride)
    return buf.reshape(h, stride)[:, : w * 4].reshape(h, w, 4).copy()
