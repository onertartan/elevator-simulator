"""
gui/tabs/simulation_config.py
==============================
Tab 4: 'Simulation Configuration'. Ported from the MATLAB source:

  * Data type button group (dataTypeChanged callback):
      - 'New Traffic' (default)          -> dataType=1, fileName=""
      - 'Recorded Traffic'               -> dataType=2, pick a .mat file
      - 'New Traffic with Custom Initials'-> dataType=3, pick a .xlsx file
    plus Number of initial passengers, 'parameter search' checkbox,
    Number of runs [1..Inf]=1.
  * Simulation duration [0..Inf]=15, Number of simulations [1..Inf]=1,
    Reference time [0..Inf].
  * Dispatch group: 'Dispatch when new call registered' (default) vs
    'Dispatch period' + spinner [1..Inf]=1 (decisionPeriod=Inf when
    one-shot is selected).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QSpinBox, QCheckBox, QRadioButton, QButtonGroup, QFileDialog
)

BIG = 2_000_000_000  # stand-in for Inf in integer spinboxes


class SimulationConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_type = 1
        self.file_name = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ---- Data type group ------------------------------------------------
        data_box = QGroupBox("Data type")
        db = QGridLayout(data_box)
        self.new_traffic_rb = QRadioButton("New Traffic")
        self.new_traffic_rb.setChecked(True)
        self.recorded_traffic_rb = QRadioButton("Recorded Traffic")
        self.custom_initials_rb = QRadioButton("New Traffic with Custom Initials")
        group = QButtonGroup(self)
        for i, rb in enumerate((self.new_traffic_rb, self.recorded_traffic_rb,
                                self.custom_initials_rb)):
            group.addButton(rb)
            db.addWidget(rb, i, 0)

        db.addWidget(QLabel("Number of initial passengers"), 3, 0)
        self.num_initial_passengers = QSpinBox()
        self.num_initial_passengers.setRange(0, BIG)
        self.num_initial_passengers.setFixedWidth(90)
        db.addWidget(self.num_initial_passengers, 3, 1)

        self.parameter_search = QCheckBox("parameter search")
        db.addWidget(self.parameter_search, 4, 0)

        db.addWidget(QLabel("Number of runs"), 5, 0)
        self.number_of_runs = QSpinBox()
        self.number_of_runs.setRange(1, BIG)
        self.number_of_runs.setValue(1)
        self.number_of_runs.setFixedWidth(90)
        db.addWidget(self.number_of_runs, 5, 1)

        self.file_label = QLabel("")
        self.file_label.setStyleSheet("color: #777;")
        db.addWidget(self.file_label, 6, 0, 1, 2)
        db.setColumnStretch(2, 1)
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

    def _data_type_changed(self, checked):
        if not checked:
            return
        if self.new_traffic_rb.isChecked():
            self.data_type, self.file_name = 1, ""
        elif self.recorded_traffic_rb.isChecked():
            self.data_type = 2
            self.file_name, _ = QFileDialog.getOpenFileName(
                self, "Select the recorded Traffic file", "", "MAT files (*.mat)")
        else:
            self.data_type = 3
            self.file_name, _ = QFileDialog.getOpenFileName(
                self, "Select the Traffic initials file", "", "Excel files (*.xlsx)")
        self.file_label.setText(self.file_name)

    # ---- startData contribution -----------------------------------------
    def to_start_data(self):
        return {
            "parameterSearch": self.parameter_search.isChecked(),
            "numberOfRuns": self.number_of_runs.value(),
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
            "num_initial_passengers": self.num_initial_passengers.value(),
            "parameter_search": self.parameter_search.isChecked(),
            "number_of_runs": self.number_of_runs.value(),
            "simulation_duration": self.simulation_duration.value(),
            "num_simulations": self.num_simulations.value(),
            "reference_time": self.reference_time.value(),
            "one_shot": self.one_shot_rb.isChecked(),
            "dispatch_period": self.dispatch_period_spinner.value(),
        }

    def from_state(self, s):
        # restore data type without re-opening file dialogs
        for rb in (self.new_traffic_rb, self.recorded_traffic_rb,
                   self.custom_initials_rb):
            rb.blockSignals(True)
        (self.new_traffic_rb if s["data_type"] == 1 else
         self.recorded_traffic_rb if s["data_type"] == 2 else
         self.custom_initials_rb).setChecked(True)
        for rb in (self.new_traffic_rb, self.recorded_traffic_rb,
                   self.custom_initials_rb):
            rb.blockSignals(False)
        self.data_type = s["data_type"]
        self.file_name = s["file_name"]
        self.file_label.setText(self.file_name)
        self.num_initial_passengers.setValue(s["num_initial_passengers"])
        self.parameter_search.setChecked(s["parameter_search"])
        self.number_of_runs.setValue(s["number_of_runs"])
        self.simulation_duration.setValue(s["simulation_duration"])
        self.num_simulations.setValue(s["num_simulations"])
        self.reference_time.setValue(s["reference_time"])
        (self.one_shot_rb if s["one_shot"]
         else self.dispatch_period_rb).setChecked(True)
        self.dispatch_period_spinner.setValue(s["dispatch_period"])
