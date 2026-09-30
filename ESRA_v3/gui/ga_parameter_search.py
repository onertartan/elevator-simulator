"""GA grid-search settings; common algorithm budgets stay on Control Method."""
from __future__ import annotations

import copy
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ga_sweep_config import (
    CAR_PARAMS, DEFAULT_OUT, GRID_KEYS, OBJECTIVES, configuration_count,
    default_grid, default_workers, rate_range, validate_experiment, validate_grid,
)


class RateEditor(QGroupBox):
    changed = Signal()

    def __init__(self, title, values, parent=None):
        super().__init__(title, parent)
        layout = QGridLayout(self)
        self.mode = QComboBox()
        self.mode.addItems(["Start / end / step", "Explicit values"])
        layout.addWidget(self.mode, 0, 0, 1, 3)
        self.start, self.end, self.step = [QDoubleSpinBox() for _ in range(3)]
        for column, (label, spin) in enumerate(zip(
                ("Start", "End (inclusive)", "Step"),
                (self.start, self.end, self.step))):
            spin.setDecimals(6)
            spin.setRange(0, 1)
            spin.setSingleStep(0.01)
            layout.addWidget(QLabel(label), 1, column)
            layout.addWidget(spin, 2, column)
            spin.valueChanged.connect(self._changed)
        self.values_edit = QLineEdit(", ".join(f"{v:g}" for v in values))
        self.values_edit.setPlaceholderText("0.01, 0.02, 0.05")
        layout.addWidget(self.values_edit, 3, 0, 1, 3)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview, 4, 0, 1, 3)
        self.start.setValue(values[0])
        self.end.setValue(values[-1])
        self.step.setValue(0.1 if title.startswith("Crossover") else 0.01)
        self.mode.setCurrentIndex(0 if title.startswith("Crossover") else 1)
        self.mode.currentIndexChanged.connect(self._changed)
        self.values_edit.textChanged.connect(self._changed)
        self._changed()

    def values(self):
        if self.mode.currentIndex() == 0:
            return rate_range(self.start.value(), self.end.value(), self.step.value())
        try:
            return [float(token.strip()) for token in self.values_edit.text().split(",")]
        except ValueError as exc:
            raise ValueError("Enter a comma-separated list of rates.") from exc

    def _changed(self, *_):
        is_range = self.mode.currentIndex() == 0
        for spin in (self.start, self.end, self.step):
            spin.setEnabled(is_range)
        self.values_edit.setEnabled(not is_range)
        try:
            values = self.values()
            preview = ", ".join(f"{v:g}" for v in values[:12])
            self.preview.setText(f"{len(values)} values: {preview}" +
                                 (", ..." if len(values) > 12 else ""))
        except ValueError as exc:
            self.preview.setText(str(exc))
        self.changed.emit()

    def to_state(self):
        return {"mode": self.mode.currentIndex(), "start": self.start.value(),
                "end": self.end.value(), "step": self.step.value(),
                "values": self.values_edit.text()}

    def from_state(self, state):
        self.mode.setCurrentIndex(state["mode"])
        self.start.setValue(state["start"])
        self.end.setValue(state["end"])
        self.step.setValue(state["step"])
        self.values_edit.setText(state["values"])


class GAParameterSearchDialog(QDialog):
    def __init__(self, start_data, options=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run GA Parameter Search")
        self.resize(760, 720)
        self.start_data = copy.deepcopy(start_data)
        self.experiment_spec = None
        root = QVBoxLayout(self)
        self.budget_label = QLabel(
            f"Population size: {start_data['nPop']}    Generations: {start_data['G']}\n"
            f"Objective: {start_data['objectiveFunction']}\n"
            "These settings are taken from Control Method.")
        root.addWidget(self.budget_label)

        files = QFormLayout()
        initial_path = start_data.get("fileName", "") if start_data.get("dataType") == 3 else ""
        self.snapshot_edit = QLineEdit(initial_path)
        self.output_edit = QLineEdit(DEFAULT_OUT)
        files.addRow("Custom-initials workbook", self._path_row(self.snapshot_edit, self._browse_snapshot))
        files.addRow("Output folder", self._path_row(self.output_edit, self._browse_output))
        root.addLayout(files)

        grid = default_grid()
        rates = QHBoxLayout()
        self.pc = RateEditor("Crossover rate (Pc)", grid["crossoverValues"])
        self.pm = RateEditor("Mutation rate (Pm)", grid["mutationValues"])
        rates.addWidget(self.pc)
        rates.addWidget(self.pm)
        root.addLayout(rates)

        labels = {"selectionstochunif": "Stochastic uniform",
                  "selectionroulette": "Roulette-wheel",
                  "selectiontournament": "Tournament",
                  "crossoverscattered": "Scattered",
                  "crossoversinglepoint": "Single-point",
                  "crossovertwopoint": "Two-point"}
        methods = QHBoxLayout()
        self.method_boxes = {}
        for title, key in zip(("Selection", "Crossover", "Mutation"), GRID_KEYS[2:]):
            box = QGroupBox(title + " methods")
            column = QVBoxLayout(box)
            self.method_boxes[key] = {}
            for method in grid[key]:
                checkbox = QCheckBox(labels.get(method, method.capitalize()))
                checkbox.setChecked(True)
                column.addWidget(checkbox)
                self.method_boxes[key][method] = checkbox
            column.addStretch()
            methods.addWidget(box)
        root.addLayout(methods)

        effort = QGridLayout()
        self.runs = self._spin(1, 1000000, 10)
        self.seed = self._spin(0, 2000000000, 0)
        self.workers = self._spin(1, max(256, os.cpu_count() or 1), default_workers())
        self.seed_mode = QComboBox()
        self.seed_mode.addItem("CRN — shared seed per repetition", "crn")
        self.seed_mode.addItem("Independent — separate seed per task", "independent")
        for i, (name, control) in enumerate((("Runs per configuration", self.runs),
                ("Base seed", self.seed), ("Parallel workers", self.workers),
                ("Seed mode", self.seed_mode))):
            row, col = divmod(i, 2)
            effort.addWidget(QLabel(name), row, col * 2)
            effort.addWidget(control, row, col * 2 + 1)
        root.addLayout(effort)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        note = QLabel("Results: per-run objective scores, metadata and CSV summary.\n"
                      "This search optimizes a fixed snapshot. Lower objective values are better.")
        note.setWordWrap(True)
        root.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.run_button = self.buttons.button(QDialogButtonBox.Ok)
        self.run_button.setText("Run search")
        self.buttons.accepted.connect(self._accept_search)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        if options:
            self._restore(options)
        self.pc.changed.connect(self._update_summary)
        self.pm.changed.connect(self._update_summary)
        self.runs.valueChanged.connect(self._update_summary)
        self.snapshot_edit.textChanged.connect(self._update_summary)
        self.output_edit.textChanged.connect(self._update_summary)
        for boxes in self.method_boxes.values():
            for box in boxes.values():
                box.toggled.connect(self._update_summary)
        self._update_summary()

    @staticmethod
    def _spin(low, high, value):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        return spin

    def _path_row(self, edit, callback):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit)
        button = QPushButton("Browse...")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return widget

    def _browse_snapshot(self):
        path, _ = QFileDialog.getOpenFileName(self, "Custom initials", self.snapshot_edit.text(),
                                             "Excel files (*.xlsx)")
        if path:
            self.snapshot_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def grid(self):
        return validate_grid({"crossoverValues": self.pc.values(), "mutationValues": self.pm.values(),
                              **{key: [name for name, box in boxes.items() if box.isChecked()]
                                 for key, boxes in self.method_boxes.items()}})

    def _update_summary(self, *_):
        try:
            grid = self.grid()
            count = configuration_count(grid)
            factors = " × ".join(str(len(grid[key])) for key in GRID_KEYS)
            self.summary.setText(f"{factors} = {count:,} configurations\n"
                                 f"{count:,} × {self.runs.value():,} runs = "
                                 f"{count * self.runs.value():,} GA runs")
            self.run_button.setEnabled(True)
        except ValueError as exc:
            self.summary.setText(str(exc))
            self.run_button.setEnabled(False)

    def build_experiment(self):
        data = self.start_data
        spec = validate_experiment({
            "schemaVersion": 1, "grid": self.grid(),
            "snapshot": self.snapshot_edit.text().strip(),
            "outputDir": self.output_edit.text().strip(),
            "objective": OBJECTIVES.get(data["objectiveFunction"], "unsupported"),
            "populationSize": data["nPop"], "generations": data["G"],
            "runs": self.runs.value(), "baseSeed": self.seed.value(),
            "seedMode": self.seed_mode.currentData(), "workers": self.workers.value(),
            "carParams": {key: data[key] for key in CAR_PARAMS},
        })
        if not os.path.isfile(spec["snapshot"]):
            raise ValueError("Select an existing custom-initials .xlsx file.")
        if os.path.isfile(spec["outputDir"]):
            raise ValueError("The output path must be a folder.")
        return spec

    def _accept_search(self):
        try:
            self.experiment_spec = self.build_experiment()
        except ValueError as exc:
            QMessageBox.warning(self, "Parameter search", str(exc))
            return
        self.accept()

    def to_state(self):
        return {"pc": self.pc.to_state(), "pm": self.pm.to_state(),
                "methods": {key: [name for name, box in boxes.items() if box.isChecked()]
                            for key, boxes in self.method_boxes.items()},
                "runs": self.runs.value(), "seed": self.seed.value(),
                "seed_mode": self.seed_mode.currentData(), "workers": self.workers.value(),
                "output_dir": self.output_edit.text(), "snapshot": self.snapshot_edit.text()}

    def _restore(self, state):
        for name in ("pc", "pm"):
            if name in state:
                getattr(self, name).from_state(state[name])
        for key, selected in state.get("methods", {}).items():
            for name, box in self.method_boxes.get(key, {}).items():
                box.setChecked(name in selected)
        for name in ("runs", "seed", "workers"):
            if name in state:
                getattr(self, name).setValue(state[name])
        self.seed_mode.setCurrentIndex(max(0, self.seed_mode.findData(state.get("seed_mode", "crn"))))
        self.output_edit.setText(state.get("output_dir", DEFAULT_OUT))
        if not self.snapshot_edit.text():
            self.snapshot_edit.setText(state.get("snapshot", ""))
