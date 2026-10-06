"""Offscreen integration test for the difficulty-scenario dialog worker."""
from __future__ import annotations

import os
import json
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog

from gui.scenario_creator import ScenarioCreatorDialog
from scenario_fixture import write_small_reference

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dialog_creates_and_returns_workbook():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="esra_dialog_test_") as tmp:
        reference = os.path.join(tmp, "reference.xlsx")
        write_small_reference(reference)
        output = os.path.join(tmp, "dialog_generated.xlsx")
        dialog = ScenarioCreatorDialog(
            reference, stop_over_time=7.0, velocity_fps=0.5, door_opening_time=1.25)
        assert dialog.confirm_spin.value() == 1000
        assert dialog.screen_spin.value() == 150
        assert "100 full sweeps" in dialog.confirm_spin.toolTip()
        dialog.level_combo.setCurrentIndex(3)  # custom band
        dialog.low_spin.setValue(0)
        dialog.high_spin.setValue(100)
        dialog.output_edit.setText(output)
        dialog.tries_spin.setValue(1)
        dialog.screen_spin.setValue(1)
        dialog.confirm_spin.setValue(1)

        QTimer.singleShot(0, dialog._start_generation)
        assert dialog.exec() == QDialog.Accepted
        assert dialog.generated_scenario is not None
        assert dialog.generated_scenario.path == output
        assert os.path.isfile(output)
        assert dialog.generated_scenario.reference_type == "exact_optimum"
        assert dialog.generated_scenario.selection.rtol == 0
        with open(dialog.generated_scenario.metadata_path, encoding="utf-8") as stream:
            metadata = json.load(stream)
        assert metadata["door_opening_time"] == 1.25
        assert metadata["hc_protocol"]["max_sweeps"] == 100
        assert metadata["selection"]["runs"] == 1  # UI override reaches worker

    app.processEvents()
    print("PASS  scenario-creator worker returns and selects a workbook")


def test_dialog_reports_limit_without_success():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="esra_dialog_limit_") as tmp:
        reference = os.path.join(tmp, "reference.xlsx")
        write_small_reference(reference)
        dialog = ScenarioCreatorDialog(reference, stop_over_time=7, velocity_fps=0.5)
        dialog.output_edit.setText(os.path.join(tmp, "no_output.xlsx"))
        dialog.exact_calls_spin.setValue(2)
        def warning(*_):
            QTimer.singleShot(0, dialog.reject)
        with patch("gui.scenario_creator.QMessageBox.warning", side_effect=warning) as message:
            QTimer.singleShot(0, dialog._start_generation)
            assert dialog.exec() == QDialog.Rejected
        assert "call_limit" in message.call_args.args[2]
        assert dialog.generated_scenario is None
        assert not os.path.exists(dialog.output_edit.text())
    app.processEvents()
    print("PASS  worker reports exact call limit without returning a generated scenario")


def test_dialog_cancellation():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="esra_dialog_cancel_") as tmp:
        reference = os.path.join(tmp, "reference.xlsx")
        write_small_reference(reference)
        dialog = ScenarioCreatorDialog(reference, stop_over_time=7, velocity_fps=0.5)
        dialog.output_edit.setText(os.path.join(tmp, "cancelled.xlsx"))
        dialog.screen_spin.setValue(0)
        def start_and_cancel():
            dialog._start_generation()
            dialog.reject()
        QTimer.singleShot(0, start_and_cancel)
        assert dialog.exec() == QDialog.Rejected
        assert dialog.generated_scenario is None
        assert dialog.worker is None
        assert not os.path.exists(dialog.output_edit.text())
    app.processEvents()
    print("PASS  GUI cancellation finishes worker without successful output")


def test_dispatch_and_objective_selection_do_not_change_difficulty_protocol():
    from gui.main_window import ElevatorSimulatorWindow
    from unittest.mock import MagicMock
    app = QApplication.instance() or QApplication([])
    window = ElevatorSimulatorWindow()
    received = []
    for label, method in (("Conventional Information", window.control_tab.nearest_car_rb),
                          ("Destination Information", window.control_tab.metaheuristics_rb)):
        window.control_tab.objective_function.setCurrentText(label)
        assert window.control_tab.objective_function.currentText() == label
        method.setChecked(True)
        assert method.isChecked()
        fake = MagicMock()
        fake.exec.return_value = QDialog.Rejected
        with patch("gui.scenario_creator.ScenarioCreatorDialog", return_value=fake) as dialog:
            window._create_custom_initials()
            received.append(dialog.call_args)
    assert received[0] == received[1]
    assert set(received[0].kwargs) == {
        "stop_over_time", "velocity_fps", "door_opening_time", "parent"}
    assert received[0].kwargs["door_opening_time"] == window.building_tab.to_start_data()["doorOpeningTime"]
    window.deleteLater()
    app.processEvents()
    print("PASS  scenario creator receives only physics, not subsequent experiment objective")


if __name__ == "__main__":
    test_dialog_creates_and_returns_workbook()
    test_dialog_reports_limit_without_success()
    test_dialog_cancellation()
    test_dispatch_and_objective_selection_do_not_change_difficulty_protocol()
    print("\nALL SCENARIO-CREATOR DIALOG TESTS PASSED")
