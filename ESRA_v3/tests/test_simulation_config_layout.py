"""Layout regression checks for the Simulation Configuration tab."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from gui.tabs.simulation_config import SimulationConfigTab


def _grid_position(layout, widget):
    index = layout.indexOf(widget)
    assert index >= 0, f"{widget!r} is not in the data-type grid"
    return layout.getItemPosition(index)


def test_initial_passengers_is_next_to_new_traffic():
    app = QApplication.instance() or QApplication([])
    tab = SimulationConfigTab()
    grid = tab.num_initial_passengers.parentWidget().layout()

    assert _grid_position(grid, tab.new_traffic_rb) == (0, 0, 1, 1)
    assert _grid_position(
        grid, tab.num_initial_passengers_label) == (0, 1, 1, 1)
    assert _grid_position(grid, tab.num_initial_passengers) == (0, 2, 1, 1)
    assert tab.custom_initials_rb.text() == "Load Custom Initials File"
    assert tab.create_custom_initials_rb.text() == \
        "Create Difficulty-Based Custom Initials..."
    assert _grid_position(grid, tab.custom_initials_rb) == (2, 0, 1, 1)
    assert _grid_position(
        grid, tab.create_custom_initials_rb) == (3, 0, 1, 1)
    assert tab.new_traffic_rb.isChecked()

    tab.num_initial_passengers.setValue(7)
    assert tab.to_start_data()["numInitialPassengers"] == 7

    tab.set_created_custom_initials("generated.xlsx")
    assert tab.create_custom_initials_rb.isChecked()
    assert tab.to_start_data()["dataType"] == 3
    assert tab.to_state()["custom_initials_mode"] == "create"

    tab.close()
    app.processEvents()
    print("PASS  initial-passenger control is beside New Traffic")


if __name__ == "__main__":
    test_initial_passengers_is_next_to_new_traffic()
    print("\nALL SIMULATION-CONFIG LAYOUT TESTS PASSED")
