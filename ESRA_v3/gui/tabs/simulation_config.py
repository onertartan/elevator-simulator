"""
gui/tabs/simulation_config.py
==============================
Tab 4: 'Simulation Configuration'. Ported from the MATLAB source:

  * Data type button group (dataTypeChanged callback):
      - 'New Traffic' (default)          -> dataType=1, fileName=""
      - 'Recorded Traffic'               -> dataType=2, pick a .mat file
      - 'Load Custom Initials File'       -> dataType=3, pick a .xlsx file
      - 'Create Difficulty-Based Custom Initials...' -> create and use a
        measured-difficulty .xlsx file, also dataType=3
    'Number of initial passengers' is placed on the same row as 'New
    Traffic', because it applies only to that data type.
  * Simulation duration [0..Inf]=15, Number of simulations [1..Inf]=1,
    Reference time [0..Inf].
  * Dispatch group: 'Dispatch when new call registered' (default) vs
    'Dispatch period' + spinner [1..Inf]=1 (decisionPeriod=Inf when
    one-shot is selected).
"""
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QSpinBox, QRadioButton, QButtonGroup, QFileDialog
)

BIG = 2_000_000_000  # stand-in for Inf in integer spinboxes


class SimulationConfigTab(QWidget):
    custom_initials_creation_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_type = 1
        self.file_name = ""
        self.custom_initials_mode = "load"
        self._last_completed_selection = "new"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ---- Data type group ------------------------------------------------
        data_box = QGroupBox("Data type")
        db = QGridLayout(data_box)
        self.new_traffic_rb = QRadioButton("New Traffic")
        self.new_traffic_rb.setChecked(True)
        self.recorded_traffic_rb = QRadioButton("Recorded Traffic")
        self.custom_initials_rb = QRadioButton("Load Custom Initials File")
        self.create_custom_initials_rb = QRadioButton(
            "Create Difficulty-Based Custom Initials...")
        self.data_type_group = QButtonGroup(self)
        for i, rb in enumerate((self.new_traffic_rb, self.recorded_traffic_rb,
                                self.custom_initials_rb,
                                self.create_custom_initials_rb)):
            self.data_type_group.addButton(rb)
            db.addWidget(rb, i, 0)

        self.num_initial_passengers_label = QLabel(
            "Number of initial passengers")
        self.num_initial_passengers = QSpinBox()
        self.num_initial_passengers.setRange(0, BIG)
        self.num_initial_passengers.setFixedWidth(90)
        db.addWidget(self.num_initial_passengers_label, 0, 1)
        db.addWidget(self.num_initial_passengers, 0, 2)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #777;")
        db.addWidget(self.file_label, 4, 0, 1, 3)
        db.setColumnStretch(3, 1)
        layout.addWidget(data_box)

        # ---- Timing spinners -----------------------------------------------
        timing = QGridLayout()
        self.simulation_duration = QSpinBox()
        self.simulation_duration.setRange(0, BIG)
        self.simulation_duration.setValue(15)
        self.num_simulations = QSpinBox()
        self.num_simulations.setRange(1, BIG)
        self.num_simulations.setValue(1)
        self.reference_time = QSpinBox()
        self.reference_time.setRange(0, BIG)
        self.reference_time.setValue(0)
        for w in (self.simulation_duration, self.num_simulations,
                  self.reference_time):
            w.setFixedWidth(110)
        timing.addWidget(QLabel("Simulation duration"), 0, 0)
        timing.addWidget(self.simulation_duration, 0, 1)
        timing.addWidget(QLabel("Number of simulations"), 1, 0)
        timing.addWidget(self.num_simulations, 1, 1)
        timing.addWidget(QLabel("Reference time"), 2, 0)
        timing.addWidget(self.reference_time, 2, 1)
        timing.setColumnStretch(2, 1)
        layout.addLayout(timing)

        # ---- Dispatch period group -----------------------------------------
        dispatch_box = QGroupBox("Dispatch")
        dp = QVBoxLayout(dispatch_box)
        self.one_shot_rb = QRadioButton("Dispatch when new call registered")
        self.one_shot_rb.setChecked(True)
        self.dispatch_period_rb = QRadioButton()
        dispatch_group = QButtonGroup(self)
        dispatch_group.addButton(self.one_shot_rb)
        dispatch_group.addButton(self.dispatch_period_rb)

        dp.addWidget(self.one_shot_rb)
        period_row = QHBoxLayout()
        period_row.addWidget(self.dispatch_period_rb)
        period_row.addWidget(QLabel("Dispatch period"))
        self.dispatch_period_spinner = QSpinBox()
        self.dispatch_period_spinner.setRange(1, BIG)
        self.dispatch_period_spinner.setValue(1)
        self.dispatch_period_spinner.setFixedWidth(90)
        period_row.addWidget(self.dispatch_period_spinner)
        period_row.addStretch()
        dp.addLayout(period_row)
        layout.addWidget(dispatch_box)
        layout.addStretch()

        # ---- wiring (dataTypeChanged) ------------------------------------
        self.new_traffic_rb.toggled.connect(self._data_type_changed)
        self.recorded_traffic_rb.toggled.connect(self._data_type_changed)
        self.custom_initials_rb.toggled.connect(self._data_type_changed)
        self.create_custom_initials_rb.toggled.connect(
            self._data_type_changed)

    def _data_type_changed(self, checked):
        if not checked:
            return
        if self.new_traffic_rb.isChecked():
            self.data_type, self.file_name = 1, ""
            self._last_completed_selection = "new"
        elif self.recorded_traffic_rb.isChecked():
            self.data_type = 2
            path, _ = QFileDialog.getOpenFileName(
                self, "Select the recorded Traffic file", "", "MAT files (*.mat)")
            if not path:
                self.cancel_custom_initials_creation()
                return
            self.file_name = path
            self._last_completed_selection = "recorded"
        elif self.custom_initials_rb.isChecked():
            self.data_type = 3
            path, _ = QFileDialog.getOpenFileName(
                self, "Select the Traffic initials file", "", "Excel files (*.xlsx)")
            if not path:
                self.cancel_custom_initials_creation()
                return
            self.file_name = path
            self.custom_initials_mode = "load"
            self._last_completed_selection = "load"
        else:
            self.custom_initials_creation_requested.emit()
            return
        self.file_label.setText(self.file_name)

    def set_created_custom_initials(self, path):
        """Select a workbook returned by the difficulty-creation dialog."""
        self._set_data_type_button(self.create_custom_initials_rb)
        self.data_type = 3
        self.file_name = os.path.abspath(path)
        self.custom_initials_mode = "create"
        self._last_completed_selection = "create"
        self.file_label.setText(self.file_name)

    def cancel_custom_initials_creation(self):
        """Restore the last completed choice after closing the dialog."""
        choices = {
            "new": self.new_traffic_rb,
            "recorded": self.recorded_traffic_rb,
            "load": self.custom_initials_rb,
            "create": self.create_custom_initials_rb,
        }
        self._set_data_type_button(
            choices.get(self._last_completed_selection,
                        self.new_traffic_rb))

    def _set_data_type_button(self, selected):
        buttons = (self.new_traffic_rb, self.recorded_traffic_rb,
                   self.custom_initials_rb, self.create_custom_initials_rb)
        for button in buttons:
            button.blockSignals(True)
        selected.setChecked(True)
        for button in buttons:
            button.blockSignals(False)

    # ---- startData contribution -----------------------------------------
    def to_start_data(self):
        return {
            "refTime": self.reference_time.value(),
            "endTime": self.simulation_duration.value(),
            "numSimulations": self.num_simulations.value(),
            "decisionPeriod": (self.dispatch_period_spinner.value()
                               if self.dispatch_period_rb.isChecked()
                               else float("inf")),
            "dataType": self.data_type,
            "fileName": self.file_name,
            "numInitialPassengers": self.num_initial_passengers.value(),
        }

    def to_state(self):
        return {
            "data_type": self.data_type,
            "file_name": self.file_name,
            "custom_initials_mode": self.custom_initials_mode,
            "num_initial_passengers": self.num_initial_passengers.value(),
            "simulation_duration": self.simulation_duration.value(),
            "num_simulations": self.num_simulations.value(),
            "reference_time": self.reference_time.value(),
            "one_shot": self.one_shot_rb.isChecked(),
            "dispatch_period": self.dispatch_period_spinner.value(),
        }

    def from_state(self, s):
        # restore data type without re-opening file dialogs
        mode = s.get("custom_initials_mode", "load")
        selected = (self.new_traffic_rb if s["data_type"] == 1 else
                    self.recorded_traffic_rb if s["data_type"] == 2 else
                    self.create_custom_initials_rb if mode == "create" else
                    self.custom_initials_rb)
        self._set_data_type_button(selected)
        self.data_type = s["data_type"]
        self.file_name = s["file_name"]
        self.custom_initials_mode = mode
        self._last_completed_selection = (
            "new" if self.data_type == 1 else
            "recorded" if self.data_type == 2 else mode)
        self.file_label.setText(self.file_name)
        self.num_initial_passengers.setValue(s["num_initial_passengers"])
        self.simulation_duration.setValue(s["simulation_duration"])
        self.num_simulations.setValue(s["num_simulations"])
        self.reference_time.setValue(s["reference_time"])
        (self.one_shot_rb if s["one_shot"]
         else self.dispatch_period_rb).setChecked(True)
        self.dispatch_period_spinner.setValue(s["dispatch_period"])
