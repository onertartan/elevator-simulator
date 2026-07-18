"""
gui/worker.py
==============
Runs Experiment.run() in a QThread so the GUI stays responsive.
This is what makes Pause/Terminate work at all in the Python port
(MATLAB got away with running on the UI thread because pause()/drawnow
pumped its event queue - Qt has no such luxury without freezing).

Wire-up in ElevatorSimulatorWindow (replaces the _start/_pause/_terminate
bodies from the GUI-only version):

    from experiment import Experiment
    from gui.worker import ExperimentWorker

    def _start(self):
        start_data = self.build_start_data()
        if start_data["INCmin"] + start_data["INTmin"] > 100:
            QMessageBox.warning(self, "Alert",
                                "Sum of intervals cannot be greater than 100.")
            return
        self._reset_flags()
        # Build the decision maker from the Control Method tab (MATLAB
        # start callback equivalent). Metaheuristics remain TODO:
        from types import SimpleNamespace
        from dispatchers import NearestCarDispatcher
        if start_data["controlMethod"] == "NearestCar":
            start_data["decisionMaker"] = NearestCarDispatcher(
                SimpleNamespace(**start_data))
        else:
            QMessageBox.warning(self, "Not ported yet",
                                "Only Nearest Car Method is available so "
                                "far; GA/ACO/PSO/DE ports are pending.")
            return
        # Simulator statics, exactly as the MATLAB start callback set them:
        from simulator import Simulator
        Simulator.getSetEndTime(start_data["endTime"])
        Simulator.setgetSpeed(start_data["displaySpeed"])
        Simulator.getSetDisplayTrafficFlow(start_data["displayTrafficFlow"])
        Simulator.getSetDisplayTabularData(start_data["displayTabularData"])

        self.experiment = Experiment()
        self.worker = ExperimentWorker(self.experiment, start_data, self)
        self.worker.error.connect(lambda m: QMessageBox.critical(self, "Experiment error", m))
        self.worker.finished.connect(lambda: self.toolbar.start_btn.setEnabled(True))
        self.worker.frame.connect(self.display_tab.render_frame)  # animation
        self.toolbar.start_btn.setEnabled(False)
        self.worker.start()

    def _pause(self):
        if self.pause_flag:                       # resume
            self.pause_flag = False
            self.experiment.requestResume()
            self.toolbar.pause_btn.setText("Pause")
        else:                                     # pause
            self.pause_flag = True
            self.experiment.requestPause()
            self.toolbar.pause_btn.setText("Continue")

    def _terminate(self):
        self.stop_flag = True
        self.pause_flag = False
        if getattr(self, "experiment", None):
            self.experiment.requestExit()         # wakes a paused worker too
        self.toolbar.pause_btn.setText("Pause")
        # [D5] the widget clean-up MATLAB did inside terminationCheck:
        self.display_tab.clear_all()
        self.display_tab.flow_view.setVisible(False)

THREAD-SAFETY NOTE (important):
Simulator.displayTraffic(...) receives `app` and in MATLAB drew directly
into app widgets. In Qt, touching widgets from this worker thread is
undefined behaviour. displayTraffic must hand its data to the GUI thread
instead - the simplest pattern is to emit this worker's `frame` signal
(signals are thread-safe) and let a GUI slot do the drawing:

    # inside Simulator.displayTraffic(...):
    if app is not None and hasattr(app, "worker"):
        app.worker.frame.emit({"cars": ..., "waiting_up": ..., ...})

    # in ElevatorSimulatorWindow._start, after creating the worker:
    self.worker.frame.connect(self.display_tab.render_frame)
"""
from PySide6.QtCore import QThread, Signal


class ExperimentWorker(QThread):
    """Hosts one Experiment.run() call on a background thread."""

    error = Signal(str)     # emitted with a traceback string on failure
    frame = Signal(object)  # optional: displayTraffic -> GUI payloads

    def __init__(self, experiment, start_data, app_window, parent=None):
        super().__init__(parent)
        self.experiment = experiment
        self.start_data = start_data
        self.app_window = app_window

    def run(self):
        try:
            self.experiment.run(self.start_data, self.app_window)
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())
