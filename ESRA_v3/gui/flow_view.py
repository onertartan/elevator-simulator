"""
gui/flow_view.py
=================
GUI-thread renderer for the frames built by Simulator.displayTraffic.
Implemented with pyqtgraph: Qt-native, built for real-time updates, and
much faster than a Matplotlib canvas for per-timestep animation.

Visual mapping (from the MATLAB drawBackground/drawCars/drawHCs,
hall lanes widened per [N6]):
  first 2*_LANE_W cells  Up / Down hall-call lanes, each _LANE_W (=2)
                         cells wide (checkerboard greys)
  next N cells           one white 1-wide lane per car
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
  [N3] Landing platform (engine [A1]/[S8]): when the frame carries
       landingPlatform=True, one extra green-tinted column is drawn
       right of the last car lane, the x-range and axis ticks widen by
       one ("Exit"), and passengers alighting during the transfer phase
       walk from the cabin to the platform: person sprites tinted in
       the car's colour, placed at x = lerp(cabin, platform,
       alightProgress), over a dotted guide line while the walk is in
       progress. A shared walk FRACTION means every car reaches the
       platform in the same passengerTransferTime regardless of how far
       its lane is from the right edge. The walkers vanish when the
       engine clears 'alighting' (transfer counted back to zero,
       requirement 3). Frames without the flag (e.g. older recorded
       test frames) render exactly as before.
  [N4] Boarding walk (engine [A4]/[S10]): while the doors open, the
       passengers selected at a hall call keep standing at their hall
       lane (car['pendingBoard'], tinted in the serving car's colour -
       visually continuing the hall-call crowd, whose call was served
       at arrival). At door-open they walk from the lane to the cabin:
       x = lerp(lane, cabin, boardProgress), over a dotted guide line,
       grouped per direction with the usual 3-person cap + "xN" badge.
       The cabin's through-the-doors occupants exclude walkers still
       outside (load - len(boarding)), so nobody is drawn twice. The
       walkers vanish at transfer end - they are inside. Frames without
       these keys render exactly as before.
  [N5] Waiting-count badge: with 'Show waiting counts' enabled
       (Display tab, default on), every hall call carries a small
       white-filled SQUARE badge (side 0.50 - a quarter of the
       widened [N6] hall lane) showing the exact number of waiting
       passengers, top-left of the lane cell, while the person icons
       still cap at 3. Disabled -> the pre-[N5] look: icons plus an "xN" label
       only when the crowd exceeds 3. The legacy (non-sprite)
       renderer always shows the count inside the hall-call circle,
       as in MATLAB, regardless of the toggle.
  [N6] The two hall-call lanes are _LANE_W (=2) cells wide - double
       a car lane - giving the waiting crowds and [N5] badges room.
       Every x-position derives from _LANE_W / _lane_x(): lane
       centres 1.5 and 3.5, car i's lane starts at i + 2*_LANE_W-0.5
       (cabin centre i + 2*_LANE_W), the platform column sits at
       numCars + 2*_LANE_W + 1, and the [N3]/[N4] walk animations
       lerp between those endpoints - the boarding walk starts at
       the widened lane's centre and still ends at the cabin centre.
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
_LANE_W = 2       # [N6] hall-call lane width in cells (car lanes are 1)


def _lane_x(dir_: int) -> float:
    """[N6] centre x of the Up (dir 1) / Down (dir 2) hall lane."""
    return 0.5 + _LANE_W * (dir_ - 0.5)


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
        self._show_wait_counts = True               # [N5]
        self._last_frame = None
        self._platform_x: Optional[float] = None    # [N3] column centre

    # ------------------------------------------------------------------
    def set_use_sprites(self, enabled: bool) -> None:
        """Toggle sprite graphics; re-renders the last frame if any."""
        self._use_sprites = bool(enabled)
        if self._last_frame is not None:
            self.render_frame(self._last_frame)

    def set_show_wait_counts(self, enabled: bool) -> None:
        """[N5] Toggle the per-hall-call waiting-count badges;
        re-renders the last frame if any."""
        self._show_wait_counts = bool(enabled)
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
        platform = bool(frame.get("landingPlatform"))           # [N3]
        self._platform_x = (float(numCars + 2 * _LANE_W + 1)
                            if platform else None)
        extra = 1 if platform else 0
        plot = self.plotItem

        plot.clear()
        # ---- background checkerboard (drawBackground) -----------------
        img = np.ones((nf, 2 * _LANE_W + numCars + extra, 3))
        img[0::2, 0:_LANE_W, :] = 0.85               # [N6] Up lane
        img[1::2, 0:_LANE_W, :] = 0.70
        img[0::2, _LANE_W:2 * _LANE_W, :] = 0.70     # [N6] Down lane
        img[1::2, _LANE_W:2 * _LANE_W, :] = 0.85
        if platform:                                            # [N3]
            img[0::2, -1] = (0.88, 0.95, 0.88)   # landing platform,
            img[1::2, -1] = (0.78, 0.90, 0.78)   # green checkerboard
        self._image = pg.ImageItem((img * 255).astype(np.ubyte),
                                   axisOrder="row-major")
        # imagesc semantics: cell centres on integer coordinates, y up
        self._image.setRect(QRectF(0.5, 0.5,
                                   numCars + 2 * _LANE_W + extra, nf))
        plot.addItem(self._image)

        traffic = frame["traffic"]
        plot.setTitle(
            f"% {traffic['inc']} incoming  % {traffic['int']} interfloor  "
            f"% {traffic['out']} outgoing &nbsp;&nbsp; "
            f"Simulation time: {frame['time']:g}")

        # ---- shaft walls: dashed guides bounding each car lane [V3] ----
        shaft_pen = pg.mkPen(QColor("#7c848d"), width=1, style=Qt.DashLine)
        for k in range(numCars + 1):        # x = 4.5, 5.5, ... [N6]
            xw = 0.5 + 2 * _LANE_W + k
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
        ticks = [(_lane_x(1), "Up"), (_lane_x(2), "Down")] + [
            (i + 2 * _LANE_W, f"Car-{i}") for i in range(1, numCars + 1)]
        if platform:                                            # [N3]
            ticks.append((numCars + 2 * _LANE_W + 1, "Exit"))
        bottom.setTicks([ticks])
        # [V1] with the aspect locked, the Y range is authoritative: the
        # X range recomputes itself to keep cells square, centring the
        # building horizontally in whatever width the widget has.
        plot.setXRange(0.5, numCars + 2 * _LANE_W + 0.5 + extra,
                       padding=0)
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
            x0 = cid + 2 * _LANE_W - 0.5                        # [N6]
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
            label.setPos(cid + 2 * _LANE_W, floor)
            plot.addItem(label)

            # alighting passengers walking to the landing platform [N3]
            self._draw_walkers_simple(plot, car, colour)

            # boarders standing at / walking from the hall lane [N4]
            self._draw_boarders_simple(plot, car, colour)

        # ---- hall calls (drawHCs) ---------------------------------------
        for dir_, calls in flow["hallCalls"].items():
            dir_ = int(dir_)
            for hc in calls:
                floor = hc["floor"]
                lx = _lane_x(dir_)                              # [N6]
                colour = (QColor("white") if hc["carId"] == 0
                          else Car.color(hc["carId"]))
                circ = QGraphicsEllipseItem(lx - 0.5, floor - 0.5, 1, 1)
                circ.setBrush(QBrush(colour))
                circ.setPen(_EDGE_PEN)
                plot.addItem(circ)

                xs = [lx - 0.5, lx, lx + 0.5]
                ys = [floor, floor + 1.5 - dir_, floor]   # up:+.5 / down:-.5
                plot.addItem(pg.PlotDataItem(xs, ys, pen=_WHITE_PEN))

                count = pg.TextItem(str(hc["waitingCount"]), color="k",
                                    anchor=(0.5, 0.5))
                count.setFont(QFont("Segoe UI", 11, QFont.Bold))
                count.setPos(lx, floor)
                plot.addItem(count)

    # ------------------------------------------------------------------
    def _render_sprites(self, plot, flow) -> None:
        """Cabin/person sprite renderer (see module docstring)."""
        # ---- cars: cabins with opening doors ---------------------------
        for car in flow["cars"]:
            cid, floor = car["id"], car["floor"]
            x0 = cid + 2 * _LANE_W - 0.5                        # [N6]
            colour = Car.color(cid)
            doors_open = car["stopOverCounter"] != 0

            self._add_sprite(plot, sprites.cabin_sprite(colour, doors_open),
                             x0 + 0.03, floor - 0.47, 0.94, 0.94)

            # occupants visible through the open doors (up to 3);
            # boarding walkers still outside are not drawn inside [N4]
            n_inside = max(car["load"] - len(car.get("boarding", [])), 0)
            if doors_open and n_inside > 0:
                n = min(n_inside, 3)
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
            # outline so light palette colours (yellow/orange cars)
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

            # alighting passengers walking to the landing platform [N3]
            self._draw_walkers_sprites(plot, car, colour)

            # boarders standing at / walking from the hall lane [N4]
            self._draw_boarders_sprites(plot, car, colour)

        # ---- hall calls: waiting people + direction arrow ----------------
        for dir_, calls in flow["hallCalls"].items():
            dir_ = int(dir_)
            for hc in calls:
                floor = hc["floor"]
                lx = _lane_x(dir_)                              # [N6]
                colour = (QColor("#5d6570") if hc["carId"] == 0
                          else QColor(Car.color(hc["carId"])))
                n_icons = max(1, min(hc["waitingCount"], 3))
                person = sprites.person_sprite(colour)
                for k in range(n_icons):
                    px = lx + (k - (n_icons - 1) / 2) * 0.26
                    self._add_sprite(plot, person,
                                     px - 0.11, floor - 0.42, 0.22, 0.55)
                if self._show_wait_counts:                      # [N5]
                    # white-filled square count badge, side = 1/4 of
                    # the widened lane, at the top-left of the lane
                    badge = QGraphicsRectItem(lx - 0.95, floor - 0.06,
                                              0.50, 0.50)
                    badge.setBrush(QBrush(QColor("white")))
                    badge.setPen(pg.mkPen("#3a4046", width=1))
                    plot.addItem(badge)
                    cnt = pg.TextItem(str(hc["waitingCount"]), color="k",
                                      anchor=(0.5, 0.5))
                    cnt.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    cnt.setPos(lx - 0.70, floor + 0.19)
                    plot.addItem(cnt)
                elif hc["waitingCount"] > 3:
                    more = pg.TextItem(f"x{hc['waitingCount']}", color="k",
                                       anchor=(0.5, 0.5))
                    more.setFont(QFont("Segoe UI", 9, QFont.Bold))
                    more.setPos(lx, floor + 0.36)
                    plot.addItem(more)

                up = dir_ == 1
                apex = floor + (0.44 if up else -0.44)
                base = floor + (0.26 if up else -0.26)
                ax = lx + _LANE_W / 2 - 0.10
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
    # [N3] alighting-walk helpers (shared geometry for both renderers)
    # ------------------------------------------------------------------
    def _walk_x(self, car) -> Optional[float]:
        """Walker x-position: lerp(cabin centre, platform centre, progress).
        None when there is nothing to draw (no walkers / no platform)."""
        if self._platform_x is None or not car.get("alighting"):
            return None
        prog = min(1.0, max(0.0, float(car.get("alightProgress", 0.0))))
        x_from = car["id"] + 2 * _LANE_W         # cabin centre [N6]
        return x_from + (self._platform_x - x_from) * prog

    def _draw_walkers_sprites(self, plot, car, colour) -> None:
        """Person sprites in the car's colour walking to the platform,
        over a dotted guide line from the cabin doors to the platform."""
        wx = self._walk_x(car)
        if wx is None:
            return
        floor = car["floor"]
        guide = QColor(colour)
        guide.setAlpha(110)
        plot.addItem(pg.PlotDataItem(
            [car["id"] + 2 * _LANE_W + 0.5, self._platform_x],
            [floor, floor],
            pen=pg.mkPen(guide, width=2, style=Qt.DotLine)))
        self._draw_person_group(plot, len(car["alighting"]), wx, floor,
                                colour)

    def _draw_walkers_simple(self, plot, car, colour) -> None:
        """Legacy-mode walkers: a filled dot in the car's colour sliding
        along the floor line towards the platform column."""
        wx = self._walk_x(car)
        if wx is None:
            return
        floor = car["floor"]
        dot = QGraphicsEllipseItem(wx - 0.18, floor - 0.18, 0.36, 0.36)
        dot.setBrush(QBrush(colour))
        dot.setPen(_EDGE_PEN)
        plot.addItem(dot)
        n = len(car["alighting"])
        if n > 1:
            cnt = pg.TextItem(str(n), color="k", anchor=(0.5, 0.5))
            cnt.setFont(QFont("Segoe UI", 9, QFont.Bold))
            cnt.setPos(wx, floor + 0.34)
            plot.addItem(cnt)

    # ------------------------------------------------------------------
    # [N4] boarding-walk helpers (hall lane -> cabin)
    # ------------------------------------------------------------------
    def _draw_person_group(self, plot, count, x, floor, colour) -> None:
        """Up to 3 person sprites fanned around x, with an "xN" badge
        beyond that (same convention as the hall-call crowds)."""
        n = min(count, 3)
        person = sprites.person_sprite(QColor(colour))
        for k in range(n):
            px = x + (k - (n - 1) / 2) * 0.26
            self._add_sprite(plot, person, px - 0.11, floor - 0.42,
                             0.22, 0.55)
        if count > 3:
            more = pg.TextItem(f"x{count}", color="k", anchor=(0.5, 0.5))
            more.setFont(QFont("Segoe UI", 9, QFont.Bold))
            more.setPos(x, floor + 0.36)
            plot.addItem(more)

    @staticmethod
    def _by_dir(entries):
        """Group [{'id', 'dir'}, ...] into {dir: [ids]}."""
        out = {}
        for e in entries:
            out.setdefault(int(e["dir"]), []).append(e["id"])
        return out

    def _draw_boarders_sprites(self, plot, car, colour) -> None:
        """[N4] Standing crowd at the hall lane while the doors open,
        then person sprites walking lane -> cabin during the transfer
        phase, over a dotted guide line in the car's colour."""
        floor = car["floor"]
        cabin_x = car["id"] + 2 * _LANE_W                       # [N6]
        for dir_, ids in self._by_dir(car.get("pendingBoard", [])).items():
            self._draw_person_group(plot, len(ids), _lane_x(dir_), floor,
                                    colour)
        walk = car.get("boarding", [])
        if not walk:
            return
        prog = min(1.0, max(0.0, float(car.get("boardProgress", 0.0))))
        for dir_, ids in self._by_dir(walk).items():
            lane = _lane_x(dir_)                                # [N6]
            guide = QColor(colour)
            guide.setAlpha(110)
            plot.addItem(pg.PlotDataItem(
                [lane, car["id"] + 2 * _LANE_W - 0.5], [floor, floor],
                pen=pg.mkPen(guide, width=2, style=Qt.DotLine)))
            wx = lane + (cabin_x - lane) * prog
            self._draw_person_group(plot, len(ids), wx, floor, colour)

    def _draw_boarders_simple(self, plot, car, colour) -> None:
        """[N4] Legacy-mode boarders: filled dots at the hall lane while
        the doors open, sliding towards the cabin during the transfer."""
        floor = car["floor"]
        cabin_x = car["id"] + 2 * _LANE_W                       # [N6]

        def dot(x, count):
            d = QGraphicsEllipseItem(x - 0.18, floor - 0.18, 0.36, 0.36)
            d.setBrush(QBrush(colour))
            d.setPen(_EDGE_PEN)
            plot.addItem(d)
            if count > 1:
                c = pg.TextItem(str(count), color="k", anchor=(0.5, 0.5))
                c.setFont(QFont("Segoe UI", 9, QFont.Bold))
                c.setPos(x, floor + 0.34)
                plot.addItem(c)

        for dir_, ids in self._by_dir(car.get("pendingBoard", [])).items():
            dot(_lane_x(dir_), len(ids))
        walk = car.get("boarding", [])
        if walk:
            prog = min(1.0, max(0.0, float(car.get("boardProgress", 0.0))))
            for dir_, ids in self._by_dir(walk).items():
                lane = _lane_x(dir_)                            # [N6]
                dot(lane + (cabin_x - lane) * prog, len(ids))

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