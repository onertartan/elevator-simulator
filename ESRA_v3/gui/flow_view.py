"""
gui/flow_view.py
=================
GUI-thread renderer for the frames built by Simulator.displayTraffic.
Implemented with pyqtgraph: Qt-native, built for real-time updates, and
much faster than a Matplotlib canvas for per-timestep animation.

Visual mapping (1:1 with the MATLAB drawBackground/drawCars/drawHCs):
  columns 1..2         Up / Down hall-call lanes (checkerboard greys)
  columns 3..N+2       one white lane per car
  car                  1x1 square in Car.color(id), centred on its floor
  car load             number drawn on the car
  car direction        white chevron (flat while stopped over)
  destination floors   circles in the car's lane
  hall call            circle in its lane - white while unassigned,
                       otherwise the assigned car's colour - with an
                       up/down chevron and the waiting-passenger count

   [N1] Destination circles show the number of passengers alighting at
       that floor (sprite renderer), fed by the car's 'alight' map
       added in simulator.drawCars [S8]; missing map -> shows 0.
  [N2] Hall-call direction arrows are tinted in the ASSIGNED CAR's
       colour (grey until assigned), matching the waiting-person
       sprites; orientation alone conveys up/down. The green/red
       triangle above a cabin is unchanged (it shows the car's own
       travel direction, not an assignment).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (QGraphicsRectItem, QGraphicsEllipseItem,
                               QGraphicsPolygonItem)
from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF

from car import Car  # single source of truth for the car colour palette
from . import sprites

pg.setConfigOptions(antialias=True, background="w", foreground="k")

_WHITE_PEN = pg.mkPen("w", width=2)
_EDGE_PEN = pg.mkPen(QColor("#666666"), width=1)
_FLOOR_FONT = QFont("Segoe UI", 10, QFont.Bold)     # [V4]


class TrafficFlowView(pg.PlotWidget):
    """Renders one Simulator frame at a time (slot: render_frame)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.setMouseEnabled(x=False, y=False)
        vb = self.plotItem.getViewBox()
        vb.setDefaultPadding(0.02)
        vb.setAspectLocked(True, ratio=1.0)     # [V1] square cells
        self.plotItem.hideAxis("left")          # [V4] numbers drawn in-plot
        self._image = pg.ImageItem(axisOrder="row-major")
        self.addItem(self._image)
        self._use_sprites = True
        self._last_frame = None

    # ------------------------------------------------------------------
    def set_use_sprites(self, enabled: bool) -> None:
        """Toggle sprite graphics; re-renders the last frame if any."""
        self._use_sprites = bool(enabled)
        if self._last_frame is not None:
            self.render_frame(self._last_frame)

    def render_frame(self, frame: Dict[str, Any]) -> None:
        if frame.get("clear"):
            self.clear_view()
            return
        flow = frame.get("flow")
        if flow is None:
            return  # traffic-flow display disabled for this frame
        self._last_frame = frame

        nf = frame["nf"]
        numCars = frame["numCars"]
        plot = self.plotItem

        plot.clear()
        # ---- background checkerboard (drawBackground) -----------------
        img = np.ones((nf, 2 + numCars, 3))
        img[0::2, 0, :] = 0.85
        img[1::2, 0, :] = 0.70
        img[0::2, 1, :] = 0.70
        img[1::2, 1, :] = 0.85
        self._image = pg.ImageItem((img * 255).astype(np.ubyte),
                                   axisOrder="row-major")
        # imagesc semantics: cell centres on integer coordinates, y up
        self._image.setRect(QRectF(0.5, 0.5, numCars + 2, nf))
        plot.addItem(self._image)

        traffic = frame["traffic"]
        plot.setTitle(
            f"% {traffic['inc']} incoming  % {traffic['int']} interfloor  "
            f"% {traffic['out']} outgoing &nbsp;&nbsp; "
            f"Simulation time: {frame['time']:g}")

        # ---- shaft walls: dashed guides bounding each car lane [V3] ----
        shaft_pen = pg.mkPen(QColor("#7c848d"), width=1, style=Qt.DashLine)
        for k in range(numCars + 1):            # x = 2.5, 3.5, ... N+2.5
            xw = 2.5 + k
            plot.addItem(pg.PlotDataItem([xw, xw], [0.5, nf + 0.5],
                                         pen=shaft_pen))

        # ---- floor numbers beside the Up lane [V4] ---------------------
        for f in range(1, nf + 1):
            num = pg.TextItem(str(f), color="k", anchor=(1, 0.5))
            num.setFont(_FLOOR_FONT)
            num.setPos(0.46, f)                 # right-aligned to x=0.46
            plot.addItem(num)

        # ---- axes ------------------------------------------------------
        bottom = plot.getAxis("bottom")
        ticks = [(1, "Up"), (2, "Down")] + [
            (i + 2, f"Car-{i}") for i in range(1, numCars + 1)]
        bottom.setTicks([ticks])
        # [V1] with the aspect locked, the Y range is authoritative: the
        # X range recomputes itself to keep cells square, centring the
        # building horizontally in whatever width the widget has.
        plot.setXRange(0.5, numCars + 2.5, padding=0)
        plot.setYRange(0.5, nf + 0.5, padding=0)

        if self._use_sprites:
            self._render_sprites(plot, flow)
            return
        self._render_simple(plot, flow)

    # ------------------------------------------------------------------
    def _render_simple(self, plot, flow) -> None:
        """Original MATLAB-style primitives (rectangles/circles/chevrons)."""
        # ---- cars (drawCars) -------------------------------------------
        for car in flow["cars"]:
            cid, floor = car["id"], car["floor"]
            x0 = cid + 1.5
            colour = Car.color(cid)

            rect = QGraphicsRectItem(x0, floor - 0.5, 1, 1)
            rect.setBrush(QBrush(colour))
            rect.setPen(_EDGE_PEN)
            plot.addItem(rect)

            for df in car["DF"]:  # destination floors: circles in the lane
                circ = QGraphicsEllipseItem(x0, df - 0.5, 1, 1)
                circ.setPen(_EDGE_PEN)
                circ.setBrush(QBrush(Qt.NoBrush))   # unfilled, as in MATLAB
                plot.addItem(circ)

            # direction chevron (flat white line while stopped over)
            if car["stopOverCounter"] != 0:
                xs, ys = [x0, x0 + 1], [floor, floor]
            else:
                xs = [x0, x0 + 0.5, x0 + 1]
                ys = [floor, floor + car["state"] * 0.5, floor]
            plot.addItem(pg.PlotDataItem(xs, ys, pen=_WHITE_PEN))

            label = pg.TextItem(str(car["load"]), color="k",
                                anchor=(0.5, 0.5))
            label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            label.setPos(cid + 2, floor)
            plot.addItem(label)

        # ---- hall calls (drawHCs) ---------------------------------------
        for dir_, calls in flow["hallCalls"].items():
            dir_ = int(dir_)
            for hc in calls:
                floor = hc["floor"]
                colour = (QColor("white") if hc["carId"] == 0
                          else Car.color(hc["carId"]))
                circ = QGraphicsEllipseItem(dir_ - 0.5, floor - 0.5, 1, 1)
                circ.setBrush(QBrush(colour))
                circ.setPen(_EDGE_PEN)
                plot.addItem(circ)

                xs = [dir_ - 0.5, dir_, dir_ + 0.5]
                ys = [floor, floor + 1.5 - dir_, floor]   # up:+.5 / down:-.5
                plot.addItem(pg.PlotDataItem(xs, ys, pen=_WHITE_PEN))

                count = pg.TextItem(str(hc["waitingCount"]), color="k",
                                    anchor=(0.5, 0.5))
                count.setFont(QFont("Segoe UI", 11, QFont.Bold))
                count.setPos(dir_, floor)
                plot.addItem(count)

    # ------------------------------------------------------------------
    def _render_sprites(self, plot, flow) -> None:
        """Cabin/person sprite renderer (see module docstring)."""
        # ---- cars: cabins with opening doors ---------------------------
        for car in flow["cars"]:
            cid, floor = car["id"], car["floor"]
            x0 = cid + 1.5
            colour = Car.color(cid)
            doors_open = car["stopOverCounter"] != 0

            self._add_sprite(plot, sprites.cabin_sprite(colour, doors_open),
                             x0 + 0.03, floor - 0.47, 0.94, 0.94)

            # occupants visible through the open doors (up to 3)
            if doors_open and car["load"] > 0:
                n = min(car["load"], 3)
                for k in range(n):
                    px = x0 + 0.5 + (k - (n - 1) / 2) * 0.20
                    self._add_sprite(plot,
                                     sprites.person_sprite(QColor("#3b4046")),
                                     px - 0.085, floor - 0.34, 0.17, 0.42)

            # destination floors: dashed circles in the car's colour,
            # with the number of passengers alighting there inside [V5]
            alight = car.get("alight", {})
            for df in car["DF"]:
                circ = QGraphicsEllipseItem(x0 + 0.15, df - 0.35, 0.7, 0.7)
                pen = pg.mkPen(colour, width=2, style=Qt.DashLine)
                circ.setPen(pen)
                circ.setBrush(QBrush(Qt.NoBrush))
                plot.addItem(circ)
                n_out = alight.get(df, alight.get(str(df), 0))
                cnt = pg.TextItem(str(n_out), anchor=(0.5, 0.5),
                                  color=QColor(colour).darker(140))
                cnt.setFont(QFont("Segoe UI", 11, QFont.Bold))
                cnt.setPos(x0 + 0.5, df)
                plot.addItem(cnt)

            # direction triangle above/below the cabin, in the CAR's
            # colour (orientation alone shows up/down) [V7]; dark
            # outline so light palette colours (white/yellow cars)
            # stay visible on the white lane.
            if car["stopOverCounter"] == 0 and car["state"] != 0:
                up = car["state"] > 0
                apex = floor + (0.46 if up else -0.46)
                base = floor + (0.30 if up else -0.30)
                tri = QGraphicsPolygonItem(QPolygonF([
                    QPointF(x0 + 0.5 - 0.14, base),
                    QPointF(x0 + 0.5 + 0.14, base),
                    QPointF(x0 + 0.5, apex)]))
                tri.setBrush(QBrush(colour))
                tri.setPen(pg.mkPen("#3a4046", width=1))
                plot.addItem(tri)

            # load badge (top-right corner of the cabin)
            badge = QGraphicsEllipseItem(x0 + 0.68, floor + 0.16, 0.30, 0.30)
            badge.setBrush(QBrush(QColor("white")))
            badge.setPen(pg.mkPen("#3a4046", width=1))
            plot.addItem(badge)
            label = pg.TextItem(str(car["load"]), color="k",
                                anchor=(0.5, 0.5))
            label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            label.setPos(x0 + 0.83, floor + 0.31)
            plot.addItem(label)

        # ---- hall calls: waiting people + direction arrow ----------------
        for dir_, calls in flow["hallCalls"].items():
            dir_ = int(dir_)
            for hc in calls:
                floor = hc["floor"]
                colour = (QColor("#5d6570") if hc["carId"] == 0
                          else QColor(Car.color(hc["carId"])))
                n_icons = max(1, min(hc["waitingCount"], 3))
                person = sprites.person_sprite(colour)
                for k in range(n_icons):
                    px = dir_ + (k - (n_icons - 1) / 2) * 0.26
                    self._add_sprite(plot, person,
                                     px - 0.11, floor - 0.42, 0.22, 0.55)
                if hc["waitingCount"] > 3:
                    more = pg.TextItem(f"x{hc['waitingCount']}", color="k",
                                       anchor=(0.5, 0.5))
                    more.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    more.setPos(dir_, floor + 0.36)
                    plot.addItem(more)

                up = dir_ == 1
                apex = floor + (0.44 if up else -0.44)
                base = floor + (0.26 if up else -0.26)
                ax = dir_ + 0.40
                tri = QGraphicsPolygonItem(QPolygonF([
                    QPointF(ax - 0.09, base), QPointF(ax + 0.09, base),
                    QPointF(ax, apex)]))
                # [V6] arrow colour = assigned car's colour (grey while
                # unassigned), matching the person sprites; direction is
                # conveyed by the arrow's orientation alone.
                tri.setBrush(QBrush(colour))
                tri.setPen(pg.mkPen("#ffffff", width=1))
                plot.addItem(tri)

    # ------------------------------------------------------------------
    @staticmethod
    def _add_sprite(plot, rgba, x, y, w, h) -> None:
        """Place an RGBA sprite into a data-coordinate rectangle.
        QImage row 0 is the sprite's TOP; ImageItem maps row 0 to the
        rect's bottom in a y-up view, so flip vertically here."""
        item = pg.ImageItem(np.ascontiguousarray(rgba[::-1]),   # [V2]
                            axisOrder="row-major")
        item.setRect(QRectF(x, y, w, h))
        plot.addItem(item)

    # ------------------------------------------------------------------
    def clear_view(self) -> None:
        """Port of Simulator.clearScreen's axes reset (GUI thread only)."""
        self.plotItem.clear()
        self.plotItem.setTitle("")