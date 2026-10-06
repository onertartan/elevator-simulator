"""
tests/test_flow_sprites.py
===========================
GUI-side tests for the sprite renderer (needs Qt; runs offscreen):

    QT_QPA_PLATFORM=offscreen python tests/test_flow_sprites.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs"))

import engine_stubs  # noqa: F401  (data_structures for car.py)
import numpy as np
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from gui import sprites
from gui.flow_view import TrafficFlowView


def test_sprite_factory():
    closed = sprites.cabin_sprite(QColor("red"), doors_open=False)
    opened = sprites.cabin_sprite(QColor("red"), doors_open=True)
    person = sprites.person_sprite(QColor("green"))
    assert closed.shape == (128, 128, 4) and opened.shape == (128, 128, 4)
    assert person.shape[0] == 128 and person.shape[2] == 4
    assert not np.array_equal(closed, opened), "door states must differ"
    assert (person[:, :, 3] == 0).any() and (person[:, :, 3] == 255).any(), \
        "person sprite needs transparent background + solid body"
    assert sprites.cabin_sprite(QColor("red"), False) is closed, "cached"
    print("PASS  sprite factory: shapes, alpha, door states, caching")


def test_orientation():
    probe = np.zeros((10, 10, 4), np.uint8)
    probe[0:2, 0:2] = [255, 0, 0, 255]          # sprite-local TOP-left
    view = TrafficFlowView()
    view.resize(200, 200)
    view.show()
    view.plotItem.setXRange(0, 1, padding=0)
    view.plotItem.setYRange(0, 1, padding=0)
    view._add_sprite(view.plotItem, probe, 0, 0, 1, 1)
    app.processEvents()
    img = view.grab().toImage()
    buf = np.frombuffer(img.constBits(), np.uint8,
                        count=img.height() * img.bytesPerLine())
    arr = buf.reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4]
    arr = arr.reshape(img.height(), img.width(), 4)          # BGRA
    reds = np.argwhere((arr[:, :, 2] > 200) & (arr[:, :, 1] < 80)
                       & (arr[:, :, 0] < 80))
    assert reds.size and reds[:, 0].mean() / img.height() < 0.5, \
        "sprite top must render at screen top (people upright)"
    print("PASS  sprite orientation (y-up view flip)")


def test_render_both_modes():
    frame = {
        "time": 5, "nf": 6, "numCars": 2,
        "traffic": {"inc": 30, "int": 40, "out": 30},
        "flow": {
            "cars": [
                {"id": 1, "floor": 2.0, "state": 1, "stopOverCounter": 0.0,
                 "load": 1, "DF": [5]},
                {"id": 2, "floor": 4.0, "state": 0, "stopOverCounter": 3.0,
                 "load": 2, "DF": []},
            ],
            "hallCalls": {1: [{"floor": 3, "carId": 1, "waitingCount": 5}],
                          2: [{"floor": 6, "carId": 0, "waitingCount": 1}]},
        },
        "tables": None, "counters": ["-"] * 6,
    }
    view = TrafficFlowView()
    view.resize(400, 500)
    view.show()
    for mode in (True, False):
        view.set_use_sprites(mode)
        view.render_frame(frame)
        app.processEvents()
        shot = view.grab().toImage()
        assert not shot.isNull() and shot.width() > 0
    print("PASS  render smoke: sprite and legacy modes")


if __name__ == "__main__":
    test_sprite_factory()
    test_orientation()
    test_render_both_modes()
    print("\nAll sprite tests passed.")
