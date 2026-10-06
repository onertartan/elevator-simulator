"""
gui/main_window.py
===================
Top-level window. Ports the MATLAB app's toolbar behaviour:

  * Start     -> assembles startData from all tabs (buttonStartButtonPushed),
                 validates INCmin + INTmin <= 100, then runs Experiment.
  * Run GA Parameter Search -> opens a separate grid editor and launches
                 the parallel snapshot optimizer with a JSON experiment.
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
    QTabWidget, QFileDialog, QMessageBox, QDialog
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
        self.ga_search_options = {}

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
        self.simulation_tab.custom_initials_creation_requested.connect(
            self._create_custom_initials)
        self.control_tab.ga_search_button.clicked.connect(self._launch_parameter_sweep)

    def _create_custom_initials(self):
        """Open the measured-difficulty scenario creator and select its file."""
        from .scenario_creator import ScenarioCreatorDialog

        car_data = self.building_tab.to_start_data()
        floor_height = float(car_data["floorHeight"])
        velocity_fps = round(
            float(car_data["carVelocity"]) / floor_height, 2)
        stop_over_time = float(
            car_data["doorOpeningTime"]
            + car_data["passengerTransferTime"]
            + car_data["doorClosingTime"])
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reference = os.path.join(
            root, "initials_files", "initials_file.xlsx")
        dialog = ScenarioCreatorDialog(
            reference, stop_over_time=stop_over_time,
            velocity_fps=velocity_fps,
            door_opening_time=float(car_data["doorOpeningTime"]), parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.generated_scenario:
            result = dialog.generated_scenario
            self.simulation_tab.set_created_custom_initials(result.path)
            QMessageBox.information(
                self, "Custom initials created",
                f"Scenario file:\n{result.path}\n\n"
                f"HC optimum hit rate (selection): "
                f"{result.difficulty:.1f}% "
                "(lower means harder for this HC protocol).\n"
                f"Hits: {result.selection.success_count}/{result.selection.runs}; "
                f"95% Wilson: {result.selection.wilson95_percent[0]:.1f}–"
                f"{result.selection.wilson95_percent[1]:.1f}%.\n"
                f"Exact objective optimum: {result.optimum_cost:.9g} s.\n"
                f"Reproducibility metadata:\n{result.metadata_path}")
        else:
            self.simulation_tab.cancel_custom_initials_creation()

    # ---- startData assembly (buttonStartButtonPushed) ------------------
    def build_start_data(self):
        data = {}
        data.update(self.building_tab.to_start_data())
        data.update(self.traffic_tab.to_start_data())
        data.update(self.control_tab.to_start_data())
        data.update(self.simulation_tab.to_start_data())
        data.update(self.display_tab.to_start_data())
        # Toolbar Start always runs a simulation. The engine's sequential
        # parameter-search mode is reserved for programmatic callers.
        data.update(parameterSearch=False, numberOfRuns=1)
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
        from decision import NearestCarDispatcher, GA, ExactDispatcher
        if start_data["controlMethod"] == "NearestCar":
            start_data["decisionMaker"] = NearestCarDispatcher(
                SimpleNamespace(**start_data))
        elif start_data["controlMethod"] == "Exact":
            start_data["decisionMaker"] = ExactDispatcher(SimpleNamespace(**start_data))
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
            start_data["objFun"] = objFun
            start_data["decisionMaker"] = GA(SimpleNamespace(**start_data))
        else:
            QMessageBox.warning(
                self, "Not ported yet",
                "Runnable so far: Nearest Car Method, Exact Dispatcher and "
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
        dispatcher = start_data["decisionMaker"]
        if isinstance(dispatcher, ExactDispatcher):
            worker, experiment = self.worker, self.experiment
            dispatcher.should_cancel = lambda: self.stop_flag or experiment.exitFlag
            dispatcher.progress = lambda stage, done, total: worker.status.emit(
                f"Exact Dispatcher — {stage}: {done}/{total}")
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.error.connect(
            lambda m: QMessageBox.critical(self, "Experiment error", m))
        self.worker.finished.connect(
            lambda: self.toolbar.start_btn.setEnabled(True))
        self.worker.finished.connect(self.statusBar().clearMessage)
        self.worker.frame.connect(self.display_tab.render_frame)
        self.toolbar.start_btn.setEnabled(False)
        self.tabs.setCurrentWidget(self.display_tab)
        self.worker.start()

    # ---- [W1] GA parameter search -> parallel sweep runner -----------
    @staticmethod
    def _sweep_command(config_path):
        """Pass the complete experiment as one file, including paths with spaces."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return [sys.executable,
                os.path.join(root, "analysis", "run_parallel_sweep.py"),
                "--config", os.path.abspath(config_path)]

    def _launch_parameter_sweep(self):
        """Edit the grid, persist the experiment, and launch a separate runner."""
        import subprocess
        import tempfile
        from ga_sweep_config import OBJECTIVES
        from .ga_parameter_search import GAParameterSearchDialog

        start_data = self.build_start_data()
        if (start_data.get("controlMethod") != "Metaheuristics"
                or start_data.get("algorithm") != "GA"):
            return
        if start_data.get("objectiveFunction") not in OBJECTIVES:
            QMessageBox.warning(
                self, "Parameter search",
                "Select Conventional Information or Destination Information "
                "in Control Method before starting a GA search.")
            return
        dialog = GAParameterSearchDialog(start_data, self.ga_search_options, self)
        if dialog.exec() != QDialog.Accepted:
            return
        spec = dialog.experiment_spec
        self.ga_search_options = dialog.to_state()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        try:
            os.makedirs(spec["outputDir"], exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", prefix="ga_search_request_",
                    suffix=".json", dir=spec["outputDir"], delete=False) as stream:
                json.dump(spec, stream, indent=2, ensure_ascii=False, allow_nan=False)
                config_path = stream.name
            subprocess.Popen(self._sweep_command(config_path),
                             creationflags=flags if os.name == "nt" else 0,
                             cwd=root)
        except OSError as exc:
            QMessageBox.critical(self, "Could not start parameter search", str(exc))
            return
        QMessageBox.information(
            self, "Parameter search started",
            "The parallel sweep is running in its own console window.\n"
            "Workers run at below-normal priority; closing this app "
            "does NOT stop the sweep - press Ctrl+C in that console to "
            "stop it (partial results are still saved).\n\n"
            f"Output folder:\n{spec['outputDir']}\n\n"
            "Results: .npz, optional .mat, _meta.json, _summary.csv.\n"
            "The experiment JSON and a copy of the input workbook are also saved.")

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
            "ga_parameter_search": self.ga_search_options,
        }

    def apply_state(self, state):
        self.building_tab.from_state(state["building"])
        self.traffic_tab.from_state(state["traffic"])
        self.control_tab.from_state(state["control"])
        self.simulation_tab.from_state(state["simulation"])
        self.display_tab.from_state(state["display"])
        # Migrate the old repeat count; its checkbox must not hijack Start.
        self.ga_search_options = state.get("ga_parameter_search", {
            "runs": state["simulation"].get("number_of_runs", 10)})

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
