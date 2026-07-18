"""
tests/test_flow_platform.py
============================
GUI-side tests for the landing-platform animation (flow_view [N3],
engine [A1]/[S8]). Needs Qt; runs offscreen:

    QT_QPA_PLATFORM=offscreen python tests/test_flow_platform.py
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

BASE = {"time": 12, "nf": 6, "numCars": 2,
        "traffic": {"inc": 30, "int": 40, "out": 30},
        "tables": None, "counters": ["-"] * 6}


def _frame(platform, alighting=(), prog=0.0):
    f = dict(BASE)
    if platform:
        f["landingPlatform"] = True
    f["flow"] = {"cars": [
        {"id": 1, "floor": 4.0, "state": 1, "stopOverCounter": 4.0,
         "load": 0, "DF": [6], "alight": {6: 2},
         "alighting": list(alighting), "alightProgress": prog},
        {"id": 2, "floor": 2.0, "state": 0, "stopOverCounter": 0.0,
         "load": 1, "DF": [], "alight": {}, "alighting": [],
         "alightProgress": 0.0}],
        "hallCalls": {1: [{"floor": 3, "carId": 1, "waitingCount": 2}],
                      2: []}}
    return f


def _walkers(view):
    """Person-sized sprites right of the Down lane (excludes HC crowds)."""
    out = []
    for it in view.plotItem.items:
        if isinstance(it, pg.ImageItem) and it is not view._image:
            r = it.mapRectToParent(it.boundingRect())
            if 0.20 < r.width() < 0.24 and r.center().x() > 2.5:
                out.append(r)
    return out


def test_legacy_frame_unchanged(view):
    """Frames without landingPlatform render exactly as before [N3]."""
    for mode in (True, False):
        view.set_use_sprites(mode)
        view.render_frame(_frame(False))
        app.processEvents()
    assert view._image.image.shape[1] == 4 and view._platform_x is None
    labels = [t[1] for t in view.plotItem.getAxis("bottom")._tickLevels[0]]
    assert "Exit" not in labels
    print("PASS  legacy frame: 4 columns, no Exit tick, no platform")


def test_platform_and_walkers(view):
    view.set_use_sprites(True)
    view.render_frame(_frame(True, alighting=[7, 8], prog=0.5))
    app.processEvents()
    assert view._image.image.shape[1] == 5, "platform column missing"
    labels = [t[1] for t in view.plotItem.getAxis("bottom")._tickLevels[0]]
    assert "Exit" in labels, labels
    rects = _walkers(view)
    assert len(rects) == 2, "two walkers expected"
    centre = sum(r.center().x() for r in rects) / 2
    assert abs(centre - 4.0) < 0.02, centre   # lerp(cabin 3, platform 5, .5)
    assert {round(r.center().y(), 1) for r in rects} == {3.9}   # 3.855
    print("PASS  sprite walkers: fanned around x=4.00 (=lerp 0.5), floor 4")


def test_walk_endpoints(view):
    view.set_use_sprites(True)
    for prog, exp in ((0.0, 3.0), (1.0, 5.0)):
        view.render_frame(_frame(True, alighting=[7], prog=prog))
        app.processEvents()
        (r,) = _walkers(view)
        assert abs(r.center().x() - exp) < 0.02, (prog, r.center().x())
    print("PASS  walk endpoints: prog 0 at cabin doors, prog 1 on platform")


def test_legacy_mode_dot(view):
    view.set_use_sprites(False)
    view.render_frame(_frame(True, alighting=[7, 8], prog=0.5))
    app.processEvents()
    dots = [it for it in view.plotItem.items
            if isinstance(it, QGraphicsEllipseItem)
            and abs(it.rect().width() - 0.36) < 1e-6]
    assert len(dots) == 1 and abs(dots[0].rect().center().x() - 4.0) < 1e-6
    print("PASS  legacy walker dot at lerped x, with passenger count")


def test_no_walkers_when_empty(view):
    view.set_use_sprites(True)
    view.render_frame(_frame(True))
    app.processEvents()
    assert not _walkers(view), "no walkers expected when alighting empty"
    assert view._image.image.shape[1] == 5, "platform column persists"
    print("PASS  no walkers when alighting empty; platform column persists")


if __name__ == "__main__":
    v = TrafficFlowView()
    v.resize(500, 500)
    v.show()
    test_legacy_frame_unchanged(v)
    test_platform_and_walkers(v)
    test_walk_endpoints(v)
    test_legacy_mode_dot(v)
    test_no_walkers_when_empty(v)
    print("\nAll landing-platform renderer tests passed.")
