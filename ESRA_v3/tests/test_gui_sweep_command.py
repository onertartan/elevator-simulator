"""Offscreen checks for the GA-search action and legacy settings migration."""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QDialog
from ga_sweep_config import CAR_PARAMS, load_experiment
from gui.main_window import ElevatorSimulatorWindow
from gui.ga_parameter_search import GAParameterSearchDialog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


XLSX = os.path.join(ROOT, "initials_files", "initials_file.xlsx")


def test_sweep_command():
    path = os.path.join(ROOT, "output with spaces", "experiment.json")
    assert ElevatorSimulatorWindow._sweep_command(path) == [
        sys.executable, os.path.join(ROOT, "analysis", "run_parallel_sweep.py"),
        "--config", path]
    print("PASS  search command passes the JSON path as a single argument")


def test_dialog_and_launch():
    window = ElevatorSimulatorWindow()
    window.control_tab.population_size.setValue(12)
    window.control_tab.max_iterations.setValue(3)
    window.simulation_tab.set_created_custom_initials(XLSX)
    dialog = GAParameterSearchDialog(window.build_start_data())
    dialog.pc.start.setValue(0.5)
    dialog.pc.end.setValue(0.5)
    dialog.pm.mode.setCurrentIndex(0)
    dialog.pm.start.setValue(0.01)
    dialog.pm.end.setValue(0.03)
    dialog.pm.step.setValue(0.01)
    for boxes in dialog.method_boxes.values():
        for index, box in enumerate(boxes.values()):
            box.setChecked(index == 0)
    dialog.runs.setValue(2)
    assert "6 GA runs" in dialog.summary.text()
    selections = dialog.method_boxes["selectionFunctions"]
    selections["selectionstochunif"].setChecked(False)
    assert not dialog.run_button.isEnabled()
    selections["selectionstochunif"].setChecked(True)

    with tempfile.TemporaryDirectory(prefix="esra_search_gui_") as tmp:
        dialog.output_edit.setText(tmp)
        spec = dialog.build_experiment()
        assert spec["grid"]["mutationValues"] == [0.01, 0.02, 0.03]
        assert spec["populationSize"] == 12 and spec["generations"] == 3
        assert spec["carParams"] == {key: window.build_start_data()[key] for key in CAR_PARAMS}
        restored = GAParameterSearchDialog(window.build_start_data(), dialog.to_state())
        assert restored.build_experiment() == spec
        # Verify the button -> dialog -> JSON -> process path without
        # launching a long-running external process in this UI test.
        fake = MagicMock()
        fake.exec.return_value = QDialog.Accepted
        fake.experiment_spec = spec
        fake.to_state.return_value = dialog.to_state()
        with patch("gui.ga_parameter_search.GAParameterSearchDialog", return_value=fake), \
                patch("subprocess.Popen") as launch, \
                patch("gui.main_window.QMessageBox.information"):
            window.control_tab.ga_search_button.click()
            command = launch.call_args.args[0]
            assert command[2] == "--config"
            assert load_experiment(command[3]) == spec
        restored.close()
    window.close()
    dialog.close()
    print("PASS  custom grid, common budget, persisted options and button launch")


def test_legacy_settings_do_not_redirect_start():
    window = ElevatorSimulatorWindow()
    state = window.collect_state()
    state.pop("ga_parameter_search")
    state["simulation"].update(parameter_search=True, number_of_runs=17)
    window.apply_state(state)
    assert window.ga_search_options["runs"] == 17
    assert window.build_start_data()["parameterSearch"] is False
    assert window.build_start_data()["numberOfRuns"] == 1
    assert "parameter_search" not in window.simulation_tab.to_state()
    window.control_tab.nearest_car_rb.setChecked(True)
    assert not window.control_tab.ga_search_button.isEnabled()
    window.control_tab.metaheuristics_rb.setChecked(True)
    window.control_tab.pso_rb.setChecked(True)
    assert not window.control_tab.ga_search_button.isEnabled()
    window.control_tab.ga_rb.setChecked(True)
    assert window.control_tab.ga_search_button.isEnabled()
    with patch("gui.worker.ExperimentWorker") as worker, \
            patch.object(window, "_launch_parameter_sweep") as sweep:
        window._start()
        sweep.assert_not_called()
        worker.return_value.start.assert_called_once()
        start_data = worker.call_args.args[1]
        assert start_data["decisionMaker"].parameterSearch is False
    window.close()
    print("PASS  legacy repeat migration, button availability and normal GA Start")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    test_sweep_command()
    test_dialog_and_launch()
    test_legacy_settings_do_not_redirect_start()
    print("\nAll GUI parameter-search tests passed.")
