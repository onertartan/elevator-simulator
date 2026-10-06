"""
tests/test_flow_boarding.py
============================
GUI-side tests for the boarding animation (flow_view [N4], engine
[A4]/[S10]). Needs Qt; runs offscreen:

    QT_QPA_PLATFORM=offscreen python tests/test_flow_boarding.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs"))

try:
    import engine_stubs  # noqa: F401  (data_structures for car.py)
except ImportError:
    pass

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QGraphicsEllipseItem

app = QApplication.instance() or QApplication(sys.argv)

from gui.flow_view import TrafficFlowView

BASE = {"time": 3, "nf": 6, "numCars": 2, "landingPlatform": True,
        "traffic": {"inc": 30, "int": 40, "out": 30},
        "tables": None, "counters": ["-"] * 6}


def _frame(pending=(), boarding=(), prog=0.0, load=0):
    f = dict(BASE)
    f["flow"] = {"cars": [
        {"id": 1, "floor": 3.0, "state": 1, "stopOverCounter": 5.0,
         "load": load, "DF": [], "alight": {}, "alighting": [],
         "alightProgress": 0.0,
         "pendingBoard": [{"id": i, "dir": d} for i, d in pending],
         "boarding": [{"id": i, "dir": d} for i, d in boarding],
         "boardProgress": prog},
        {"id": 2, "floor": 5.0, "state": 0, "stopOverCounter": 0.0,
         "load": 0, "DF": [], "alight": {}, "alighting": [],
         "alightProgress": 0.0, "pendingBoard": [], "boarding": [],
         "boardProgress": 0.0}],
        "hallCalls": {1: [], 2: []}}
    return f


def _persons(view, width):
    """Mapped rects of person sprites of the given data width."""
    out = []
    for it in view.plotItem.items:
        if isinstance(it, pg.ImageItem) and it is not view._image:
            r = it.mapRectToParent(it.boundingRect())
            if abs(r.width() - width) < 0.01:
                out.append(r)
    return out


def test_standing_crowd_while_doors_open(view):
    view.set_use_sprites(True)
    view.render_frame(_frame(pending=[(7, 1), (8, 1)]))
    app.processEvents()
    xs = sorted(r.center().x() for r in _persons(view, 0.22))
    assert len(xs) == 2 and abs(sum(xs) / 2 - 1.5) < 0.02, xs
    print("PASS  pendingBoard crowd stands at the Up lane (x=1.5) while doors open")


def test_walker_lerp_and_endpoints(view):
    view.set_use_sprites(True)
    # [N6] car 1 cabin centre x=5; Up lane centre x=1.5
    #      -> midpoint 3.25 at prog 0.5
    for prog, exp in ((0.0, 1.5), (0.5, 3.25), (1.0, 5.0)):
        view.render_frame(_frame(boarding=[(7, 1)], prog=prog, load=1))
        app.processEvents()
        walkers = [r for r in _persons(view, 0.22)]
        assert len(walkers) == 1, walkers
        assert abs(walkers[0].center().x() - exp) < 0.02, (prog, walkers)
    print("PASS  boarding walker: lane at prog 0, cabin centre at prog 1")


def test_occupants_exclude_walkers(view):
    view.set_use_sprites(True)
    # load 2, both still walking -> no through-door occupant silhouettes
    view.render_frame(_frame(boarding=[(7, 1), (8, 2)], prog=0.5, load=2))
    app.processEvents()
    assert len(_persons(view, 0.17)) == 0, "walkers must not double as occupants"
    assert len(_persons(view, 0.22)) == 2   # one walker per direction group
    # walkers inside (cleared) -> occupants appear
    view.render_frame(_frame(load=2))
    app.processEvents()
    assert len(_persons(view, 0.17)) == 2
    print("PASS  cabin occupants = load - boarding walkers (no double draw)")


def test_legacy_mode_dots(view):
    view.set_use_sprites(False)
    view.render_frame(_frame(pending=[(7, 2)], boarding=[(8, 1)], prog=0.5,
                             load=1))
    app.processEvents()
    dots = [it for it in view.plotItem.items
            if isinstance(it, QGraphicsEllipseItem)
            and abs(it.rect().width() - 0.36) < 1e-6]
    xs = sorted(round(d.rect().center().x(), 2) for d in dots)
    # [N6] walker midpoint (1.5 -> 5.0) = 3.25, Down lane centre = 3.5
    assert xs == [3.25, 3.5], xs
    print("PASS  legacy dots: standing at lane, walker at lerped x")


def test_backward_compat(view):
    f = _frame()
    for car in f["flow"]["cars"]:      # frames predating [S10]
        for key in ("pendingBoard", "boarding", "boardProgress"):
            car.pop(key, None)
    for mode in (True, False):
        view.set_use_sprites(mode)
        view.render_frame(f)
        app.processEvents()
    assert not _persons(view, 0.22)
    print("PASS  frames without [S10] keys render exactly as before")


if __name__ == "__main__":
    v = TrafficFlowView()
    v.resize(500, 500)
    v.show()
    test_standing_crowd_while_doors_open(v)
    test_walker_lerp_and_endpoints(v)
    test_occupants_exclude_walkers(v)
    test_legacy_mode_dots(v)
    test_backward_compat(v)
    print("\nAll boarding renderer tests passed.")
