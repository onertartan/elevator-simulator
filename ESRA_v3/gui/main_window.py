"""
gui/main_window.py
===================
Top-level window. Ports the MATLAB app's toolbar behaviour:

  * Start     -> assembles startData from all tabs (buttonStartButtonPushed),
                 validates INCmin + INTmin <= 100, resets flags. The actual
                 Experiment().run(startData, app) engine call is stubbed
                 until the MATLAB engine classes are ported to Python.
  * Pause     -> toggles pauseFlag and the button text Pause/Continue.
  * Terminate -> sets stopFlag, resets pause, clears display tables/plot.
  * Save data -> the MATLAB app saves the 'dataConf' results struct to .mat;
                 here we save the last startData/results to JSON.
  * Exit      -> saves the full UI state to savedSettings.json, closes.
  * Load the last configuration -> restores savedSettings.json.
"""
import json
import math
import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QFileDialog, QMessageBox
)

from types import SimpleNamespace

from .tabs.building_car_config import BuildingCarConfigTab
from .tabs.traffic_config import TrafficConfigTab
from .tabs.control_method import ControlMethodTab
from .tabs.simulation_config import SimulationConfigTab
from .tabs.display_tab import DisplayTab

SETTINGS_FILE = "savedSettings.json"


class Toolbar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 8, 8, 8)
        self.load_btn = QPushButton("Load the last configuration")
        row.addWidget(self.load_btn)
        row.addStretch(1)
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.terminate_btn = QPushButton("Terminate")
        for b in (self.start_btn, self.pause_btn, self.terminate_btn):
            b.setFixedWidth(90)
            row.addWidget(b)
        row.addStretch(1)
        self.save_btn = QPushButton("Save data")
        self.exit_btn = QPushButton("Exit")
        for b in (self.save_btn, self.exit_btn):
            b.setFixedWidth(90)
            row.addWidget(b)


class ElevatorSimulatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESRA - Elevator Simulator")
        self.resize(1254, 934)

        # Flags (ports of stopFlag / pauseFlag properties)
        self.stop_flag = False
        self.pause_flag = False
        self.last_start_data = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.toolbar = Toolbar()
        root.addWidget(self.toolbar)

        self.tabs = QTabWidget()
        self.building_tab = BuildingCarConfigTab()
        self.traffic_tab = TrafficConfigTab()
        self.control_tab = ControlMethodTab()
        self.simulation_tab = SimulationConfigTab()
        self.display_tab = DisplayTab()
        self.tabs.addTab(self.building_tab,
                         "Building Configuration & Car Configuration")
        self.tabs.addTab(self.traffic_tab, "Traffic Configuration")
        self.tabs.addTab(self.control_tab, "Control Method")
        self.tabs.addTab(self.simulation_tab, "Simulation Configuration")
        self.tabs.addTab(self.display_tab, "Display Tab")
        root.addWidget(self.tabs, 1)

        self.toolbar.start_btn.clicked.connect(self._start)
        self.toolbar.pause_btn.clicked.connect(self._pause)
        self.toolbar.terminate_btn.clicked.connect(self._terminate)
        self.toolbar.save_btn.clicked.connect(self._save_data)
        self.toolbar.exit_btn.clicked.connect(self._exit)
        self.toolbar.load_btn.clicked.connect(self._load_last_configuration)

    # ---- startData assembly (buttonStartButtonPushed) ------------------
    def build_start_data(self):
        data = {}
        data.update(self.building_tab.to_start_data())
        data.update(self.traffic_tab.to_start_data())
        data.update(self.control_tab.to_start_data())
        data.update(self.simulation_tab.to_start_data())
        data.update(self.display_tab.to_start_data())
        return data

    def _reset_flags(self):
        self.stop_flag = False
        self.pause_flag = False
        self.toolbar.pause_btn.setText("Pause")

    def _start(self):
        start_data = self.build_start_data()
        # Validation from the MATLAB source
        if start_data["INCmin"] + start_data["INTmin"] > 100:
            QMessageBox.warning(self, "Alert",
                                "Sum of intervals cannot be greater than 100.")
            return
        # Build the decision maker (MATLAB start-callback equivalent)
        from decision import NearestCarDispatcher
        if start_data["controlMethod"] == "NearestCar":
            start_data["decisionMaker"] = NearestCarDispatcher(
                SimpleNamespace(**start_data))
        else:
            QMessageBox.warning(
                self, "Not ported yet",
                "Only the Nearest Car Method is runnable so far; "
                "GA/ACO/PSO/DE and MDP ports are pending.")
            return
        # Simulator statics, exactly as the MATLAB start callback set them
        from simulator import Simulator
        Simulator.getSetEndTime(start_data["endTime"])
        Simulator.setgetSpeed(start_data["displaySpeed"])
        Simulator.getSetDisplayTrafficFlow(start_data["displayTrafficFlow"])
        Simulator.getSetDisplayTabularData(start_data["displayTabularData"])

        self._reset_flags()
        from experiment import Experiment
        from .worker import ExperimentWorker
        self.experiment = Experiment()
        self.worker = ExperimentWorker(self.experiment, start_data, self)
        self.worker.error.connect(
            lambda m: QMessageBox.critical(self, "Experiment error", m))
        self.worker.finished.connect(
            lambda: self.toolbar.start_btn.setEnabled(True))
        self.worker.frame.connect(self.display_tab.render_frame)
        self.toolbar.start_btn.setEnabled(False)
        self.tabs.setCurrentWidget(self.display_tab)
        self.worker.start()

    def _pause(self):
        if self.pause_flag:                        # resume
            self.pause_flag = False
            if getattr(self, "experiment", None):
                self.experiment.requestResume()
            self.toolbar.pause_btn.setText("Pause")
        else:                                       # pause
            self.pause_flag = True
            if getattr(self, "experiment", None):
                self.experiment.requestPause()
            self.toolbar.pause_btn.setText("Continue")

    def _terminate(self):
        self.stop_flag = True
        self.pause_flag = False
        if getattr(self, "experiment", None):
            self.experiment.requestExit()          # wakes a paused worker
        self.toolbar.pause_btn.setText("Pause")
        # [D5] the widget clean-up MATLAB did inside terminationCheck:
        self.display_tab.clear_all()
        self.display_tab.flow_view.clear_view()

    def _save_data(self):
        experiment = getattr(self, "experiment", None)
        if experiment is None or experiment.dataConf is None:
            QMessageBox.information(
                self, "Save data",
                "No simulation results yet - run a simulation first "
                "(MATLAB saved the dataConf from the base workspace).")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save dataConf", "dataConf.pkl", "Pickle (*.pkl)")
        if not path:
            return
        from data_conf import saveDataConf
        saveDataConf(experiment.dataConf, path)
        QMessageBox.information(self, "Saved",
                                f"dataConf saved to {path}")

    # ---- state persistence (exitButton / loadLastConfiguration) --------
    def collect_state(self):
        return {
            "building": self.building_tab.to_state(),
            "traffic": self.traffic_tab.to_state(),
            "control": self.control_tab.to_state(),
            "simulation": self.simulation_tab.to_state(),
            "display": self.display_tab.to_state(),
        }

    def apply_state(self, state):
        self.building_tab.from_state(state["building"])
        self.traffic_tab.from_state(state["traffic"])
        self.control_tab.from_state(state["control"])
        self.simulation_tab.from_state(state["simulation"])
        self.display_tab.from_state(state["display"])

    def _exit(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.collect_state(), f, indent=2)
        # MATLAB also exports a screenshot on exit (SavePanelImage)
        self.grab().save("app_screenshot.png")
        self.close()

    def _load_last_configuration(self):
        if not os.path.exists(SETTINGS_FILE):
            return
        with open(SETTINGS_FILE) as f:
            self.apply_state(json.load(f))

    @staticmethod
    def _jsonable(d):
        return {k: ("Infinity" if isinstance(v, float) and math.isinf(v) else v)
                for k, v in d.items()}
