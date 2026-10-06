"""
tests/test_flow_wait_counts.py
===============================
GUI-side tests for the waiting-count badges (flow_view [N5]).
Needs Qt; runs offscreen:

    QT_QPA_PLATFORM=offscreen python tests/test_flow_wait_counts.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyqtgraph as pg
from PySide6.QtWidgets import (QApplication, QGraphicsEllipseItem,
                               QGraphicsRectItem)

app = QApplication.instance() or QApplication(sys.argv)

from gui.flow_view import TrafficFlowView

# one car (load badge included), an Up call with 2 waiting and a Down
# call with 5 waiting (5 > icon cap of 3)
FRAME = {"time": 1, "nf": 6, "numCars": 1,
         "traffic": {"inc": 30, "int": 40, "out": 30},
         "tables": None, "counters": ["-"] * 6,
         "flow": {
             "cars": [{"id": 1, "floor": 6.0, "state": 0,
                       "stopOverCounter": 0.0, "load": 0, "DF": []}],
             "hallCalls": {1: [{"floor": 2, "carId": 0, "waitingCount": 2}],
                           2: [{"floor": 4, "carId": 1, "waitingCount": 5}]}}}


def _texts(view):
    """{(x, y): text} for every TextItem in the plot."""
    out = {}
    for it in view.plotItem.items:
        if isinstance(it, pg.TextItem):
            p = it.pos()
            out[(round(p.x(), 2), round(p.y(), 2))] = \
                it.textItem.toPlainText()
    return out


def _load_badge_circles(view):
    """0.30-wide ellipses: the cabin load badge only."""
    return [it for it in view.plotItem.items
            if isinstance(it, QGraphicsEllipseItem)
            and abs(it.rect().width() - 0.30) < 1e-6]


def _count_badge_squares(view):
    """[N5] waiting-count badges: squares of side 0.50 (a quarter of
    the widened [N6] 2-cell hall lane)."""
    return [it for it in view.plotItem.items
            if isinstance(it, QGraphicsRectItem)
            and abs(it.rect().width() - 0.50) < 1e-6]


def _person_sprites(view):
    """Mapped rects of the 0.22-wide waiting-person sprites."""
    out = []
    for it in view.plotItem.items:
        if isinstance(it, pg.ImageItem) and it is not view._image:
            r = it.mapRectToParent(it.boundingRect())
            if abs(r.width() - 0.22) < 0.01:
                out.append(r)
    return out


def test_badges_on(view):
    """[N5] default: every hall call gets an exact-count badge; the
    icon cap of 3 still applies; no 'xN' fallback text."""
    view.set_use_sprites(True)
    view.set_show_wait_counts(True)
    view.render_frame(FRAME)
    app.processEvents()

    texts = _texts(view)
    # [N6] badge text at (lane centre - 0.70, floor + 0.19):
    # Up lane centre 1.5 -> 0.8, Down lane centre 3.5 -> 2.8
    assert texts.get((0.8, 2.19)) == "2", texts
    assert texts.get((2.8, 4.19)) == "5", texts
    assert "x5" not in texts.values(), "xN fallback replaced by badge"
    assert len(_count_badge_squares(view)) == 2, "one square per call"
    assert len(_load_badge_circles(view)) == 1, "load badge stays a circle"
    squares = _count_badge_squares(view)
    centres = sorted((round(s.rect().center().x(), 2),
                      round(s.rect().center().y(), 2)) for s in squares)
    assert centres == [(0.8, 2.19), (2.8, 4.19)], \
        "squares at the top-left of the widened lanes"
    assert len(_person_sprites(view)) == 2 + 3, "icons still cap at 3"
    print("PASS  [N5] count badges on: square badges, exact counts")


def test_badges_off_restores_old_look(view):
    """Toggle off -> pre-[N5] rendering: xN text only above 3, and the
    setter re-renders the last frame by itself."""
    view.set_show_wait_counts(False)      # re-renders internally
    app.processEvents()

    texts = _texts(view)
    assert (0.8, 2.19) not in texts and (2.8, 4.19) not in texts, texts
    assert texts.get((3.5, 4.36)) == "x5", texts
    assert not _count_badge_squares(view), "no squares when toggled off"
    assert len(_load_badge_circles(view)) == 1, "only the cabin load badge"
    assert len(_person_sprites(view)) == 2 + 3
    view.set_show_wait_counts(True)
    print("PASS  [N5] toggle off restores icons + xN-over-3 look")


def test_legacy_mode_unaffected(view):
    """The non-sprite renderer always shows the in-circle count (as in
    MATLAB), independent of the toggle."""
    view.set_use_sprites(False)
    for enabled in (True, False):
        view.set_show_wait_counts(enabled)
        view.render_frame(FRAME)
        app.processEvents()
        texts = _texts(view)
        assert texts.get((1.5, 2.0)) == "2", (enabled, texts)
        assert texts.get((3.5, 4.0)) == "5", (enabled, texts)
    view.set_use_sprites(True)
    view.set_show_wait_counts(True)
    print("PASS  legacy renderer keeps its in-circle counts")


if __name__ == "__main__":
    v = TrafficFlowView()
    v.resize(500, 500)
    v.show()
    test_badges_on(v)
    test_badges_off_restores_old_look(v)
    test_legacy_mode_unaffected(v)
    print("\nAll waiting-count badge tests passed.")
