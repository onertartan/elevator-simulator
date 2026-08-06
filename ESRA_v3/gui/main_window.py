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
import sys

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
        from decision import NearestCarDispatcher, GA
        if start_data["controlMethod"] == "NearestCar":
            start_data["decisionMaker"] = NearestCarDispatcher(
                SimpleNamespace(**start_data))
        elif (start_data["controlMethod"] == "Metaheuristics"
              and start_data.get("algorithm") == "GA"):
            # Objective Function dropdown -> ported objective ([P13]);
            # objFunConventional1 and objFunDestination exist so far.
            from decision.meta.obj_funs import (objFunConventional1,
                                                objFunDestination)
            objFuns = {"Conventional Information": objFunConventional1,
                       "Destination Information": objFunDestination}
            objFun = objFuns.get(start_data["objectiveFunction"])
            if objFun is None:
                QMessageBox.warning(
                    self, "Not ported yet",
                    f"Objective function "
                    f"'{start_data['objectiveFunction']}' is not ported "
                    "yet; ported so far: 'Conventional Information' "
                    "and 'Destination Information'.")
                return
            if start_data.get("parameterSearch"):
                # [W1] GA parameter search delegates to the parallel
                # sweep runner on the custom-initials snapshot
                self._launch_parameter_sweep(start_data)
                return
            start_data["objFun"] = objFun
            start_data["decisionMaker"] = GA(SimpleNamespace(**start_data))
        else:
            QMessageBox.warning(
                self, "Not ported yet",
                "Runnable so far: Nearest Car Method and "
                "Metaheuristics/GA; ACO/PSO/DE and MDP ports are "
                "pending.")
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

    # ---- [W1] GA parameter search -> parallel sweep runner -----------
    @staticmethod
    def _sweep_command(start_data):
        """Command line for analysis/run_parallel_sweep.py assembled
        from the current GUI settings (objective, GA budget, initials
        workbook)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        objective = ("conventional"
                     if start_data["objectiveFunction"].startswith(
                         "Conventional")
                     else "destination")
        return [sys.executable,
                os.path.join(root, "analysis", "run_parallel_sweep.py"),
                "--initials", start_data["fileName"],
                "--objective", objective,
                "--pop", str(start_data["nPop"]),
                "--gens", str(start_data["G"]),
                "--runs", str(start_data["numberOfRuns"])]

    def _launch_parameter_sweep(self, start_data):
        """[W1] Run the GA parameter search through
        analysis/run_parallel_sweep.py in its own console window:
        parallel workers at below-normal priority, [P36]-compatible
        auto-saved results. Requires the fixed custom-initials
        scenario (dataType 3) so the swept snapshot is reproducible -
        the engine-internal sequential sweep is no longer reachable
        from the GUI."""
        import subprocess
        if start_data.get("dataType") != 3 or not start_data.get("fileName"):
            QMessageBox.warning(
                self, "Parameter search",
                "Parameter search optimizes a fixed scenario workbook.\n"
                "On the Simulation tab select 'New Traffic with Custom "
                "Initials', pick the initials .xlsx, then press Start "
                "again.")
            return
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(self._sweep_command(start_data),
                         creationflags=flags if os.name == "nt" else 0,
                         cwd=root)
        QMessageBox.information(
            self, "Parameter search started",
            "The parallel sweep is running in its own console window.\n"
            "Workers run at below-normal priority; closing this app "
            "does NOT stop the sweep - press Ctrl+C in that console to "
            "stop it (partial results are still saved).\n\n"
            "Results auto-save to matlab_src/results/ as\n"
            "ga_param_search_parallel_<timestamp>.npz / .mat / "
            "_meta.json.")

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
