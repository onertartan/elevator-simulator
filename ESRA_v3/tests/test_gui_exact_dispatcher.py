"""Offscreen control-method selection, settings and ExactDispatcher worker checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from decision import ExactDispatcher
from decision.exact_dispatcher import ExactDispatchCancelled, ExactDispatchError
from decision.exact_assignment import DestinationInstance, solve_exact_assignment
from gui.main_window import ElevatorSimulatorWindow
from gui.tabs.control_method import ControlMethodTab
from gui.worker import ExperimentWorker
from simulator import Simulator


class ExactDispatcherGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.old_simulator = (Simulator._speed, Simulator._displayTrafficFlow,
                              Simulator._displayTabularData, Simulator._endTime)

    def tearDown(self):
        (Simulator._speed, Simulator._displayTrafficFlow,
         Simulator._displayTabularData, Simulator._endTime) = self.old_simulator
        self.app.processEvents()

    def test_radio_order_fixed_objective_and_irrelevant_ga_options(self):
        tab = ControlMethodTab()
        layout = tab.mdp_rb.parentWidget().layout()
        self.assertEqual(layout.indexOf(tab.exact_rb) + 1, layout.indexOf(tab.mdp_rb))
        self.assertTrue(tab.exact_panel.isHidden())
        tab.objective_function.setCurrentText("Conventional Information")
        tab.exact_rb.setChecked(True)
        self.assertEqual(tab.objective_function.currentText(), "Destination Information")
        self.assertFalse(tab.objective_function.isEnabled())
        self.assertFalse(tab.ga_search_button.isEnabled())
        self.assertFalse(tab.meta_box.isEnabled())
        self.assertFalse(tab.exact_panel.isHidden())
        data = tab.to_start_data()
        self.assertEqual(data["controlMethod"], "Exact")
        self.assertEqual(data["stateUpdateTypeForNextDecision"], "fixed")
        self.assertEqual(data["exactMaxCalls"], 16)
        self.assertEqual(data["exactTimeLimitSeconds"], 120)
        self.assertNotIn("nPop", data)
        self.assertNotIn("G", data)
        tab.metaheuristics_rb.setChecked(True)
        self.assertEqual(tab.objective_function.currentText(), "Conventional Information")
        self.assertTrue(tab.objective_function.isEnabled())
        self.assertTrue(tab.ga_search_button.isEnabled())
        tab.close()

    def test_new_settings_round_trip_and_old_settings_defaults(self):
        tab = ControlMethodTab()
        legacy = tab.to_state()
        for name in ("objective_before_exact", "exact_max_calls", "exact_time_limit"):
            legacy.pop(name)
        tab.objective_function.setCurrentText("Conventional Information")
        tab.exact_rb.setChecked(True)
        tab.exact_max_calls.setValue(9)
        tab.exact_time_limit.setValue(3.25)
        state = tab.to_state()
        restored = ControlMethodTab()
        restored.from_state(state)
        self.assertEqual(restored.to_state(), state)
        restored.metaheuristics_rb.setChecked(True)
        self.assertEqual(restored.objective_function.currentText(), "Conventional Information")
        restored.from_state(legacy)
        self.assertTrue(restored.metaheuristics_rb.isChecked())
        self.assertEqual(restored.exact_max_calls.value(), 16)
        self.assertEqual(restored.exact_time_limit.value(), 120)
        for button, name in ((restored.nearest_car_rb, "NearestCar"),
                             (restored.mdp_rb, "MDP"), (restored.exact_rb, "Exact")):
            button.setChecked(True)
            self.assertEqual(restored.to_start_data()["controlMethod"], name)
        tab.close()
        restored.close()

    def test_start_builds_exact_dispatcher_and_terminate_reaches_solver(self):
        window = ElevatorSimulatorWindow()
        window.control_tab.exact_rb.setChecked(True)
        window.control_tab.exact_max_calls.setValue(7)
        window.control_tab.exact_time_limit.setValue(12.5)
        with patch("gui.worker.ExperimentWorker") as worker, \
                patch("gui.main_window.QMessageBox.warning") as warning:
            window._start()
            warning.assert_not_called()
            worker.return_value.start.assert_called_once()
            data = worker.call_args.args[1]
            dispatcher = data["decisionMaker"]
            self.assertIsInstance(dispatcher, ExactDispatcher)
            self.assertEqual(dispatcher.max_calls, 7)
            self.assertEqual(dispatcher.time_limit_seconds, 12.5)
            self.assertFalse(dispatcher.should_cancel())
            dispatcher.progress("dp", 4, 16)
            self.assertIn("dp: 4/16", worker.return_value.status.emit.call_args.args[0])
            window.experiment.requestExit()
            self.assertTrue(dispatcher.should_cancel())
            window.experiment.exitFlag = False
            window._terminate()
            self.assertTrue(dispatcher.should_cancel())
        window.close()

    def test_worker_cancellation_is_quiet_but_limits_are_reported(self):
        instance = DestinationInstance(dict(
            n_floors=5, n_cars=1, car_floor=[1], car_state=[1], car_df=[[]],
            up=[(2, 4)], dn=[]), 2, 1)
        cancelled = solve_exact_assignment(instance, should_cancel=lambda: True)
        limited = solve_exact_assignment(instance, time_limit_seconds=0)
        for error, expect_message in ((ExactDispatchCancelled(cancelled), False),
                                      (ExactDispatchError(limited), True)):
            experiment = Mock()
            experiment.run.side_effect = error
            worker = ExperimentWorker(experiment, {}, None)
            messages = []
            worker.error.connect(messages.append)
            worker.run()
            self.assertEqual(bool(messages), expect_message)
            if expect_message:
                self.assertIn("time_limit", messages[0])

    def test_real_gui_worker_completes_small_one_shot_simulation(self):
        import experiment as experiment_module
        from test_ga_custom_initials_e2e import _write_initials_workbook, _experiment_start_data
        window = ElevatorSimulatorWindow()
        window.control_tab.exact_rb.setChecked(True)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory(prefix="esra_exact_gui_e2e_") as tmp:
            workbook = os.path.join(tmp, "initials.xlsx")
            _write_initials_workbook(workbook)
            data = vars(_experiment_start_data(workbook, None))
            data.update(window.control_tab.to_start_data())
            data.update(INCmin=30, INTmin=40, displaySpeed=5,
                        displayTrafficFlow=False, displayTabularData=False)
            errors = []
            loop = QEventLoop()
            watchdog = QTimer()
            watchdog.setSingleShot(True)
            timed_out = []
            def expire():
                timed_out.append(True)
                window._terminate()
            watchdog.timeout.connect(expire)
            try:
                os.chdir(tmp)
                with patch.object(window, "build_start_data", return_value=data), \
                        patch.object(experiment_module.time, "sleep", return_value=None), \
                        patch("gui.main_window.QMessageBox.critical", side_effect=lambda *a: errors.append(a)):
                    window._start()
                    window.worker.finished.connect(loop.quit)
                    watchdog.start(10000)
                    if window.worker.isRunning():
                        loop.exec()
                    watchdog.stop()
                    self.assertTrue(window.worker.wait(5000))
                    self.app.processEvents()
                self.assertFalse(timed_out)
                self.assertFalse(errors)
                self.assertIsNotNone(window.experiment.dataConf)
                self.assertEqual(window.worker.start_data["decisionMaker"].last_status, "optimal")
                self.assertTrue(os.path.isfile(window.experiment.resultsFile))
                self.assertTrue(window.toolbar.start_btn.isEnabled())
            finally:
                os.chdir(cwd)
                window.close()


if __name__ == "__main__":
    unittest.main()
