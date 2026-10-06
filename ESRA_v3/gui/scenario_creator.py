"""Dialog for creating a measured-difficulty custom-initials workbook."""
from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from scenario_generation import (
    HC_DEFAULT_RESTARTS, HC_MAX_SWEEPS,
    ScenarioGenerationCancelled, generate_difficulty_scenario,
)


class ScenarioGenerationWorker(QThread):
    progress = Signal(int, int, str, str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, arguments: dict, parent=None):
        super().__init__(parent)
        self.arguments = arguments

    def run(self):
        def report(attempt, total, stage, score):
            score_text = "" if score is None else f"{score:.1f}%"
            self.progress.emit(attempt, total, stage, score_text)

        try:
            result = generate_difficulty_scenario(
                **self.arguments, progress=report,
                should_cancel=self.isInterruptionRequested)
        except ScenarioGenerationCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class ScenarioCreatorDialog(QDialog):
    """Collect generation settings and run the search off the GUI thread."""

    LEVELS = (
        ("Hard target (3–10% HC optimum hits)", (3.0, 10.0)),
        ("Intermediate — exploratory (20–40%)", (20.0, 40.0)),
        ("Easy target (55–75% HC optimum hits)", (55.0, 75.0)),
        ("Custom success band", None),
    )

    def __init__(self, default_reference: str, *, stop_over_time: float,
                 velocity_fps: float, door_opening_time: float = 0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Difficulty-Based Custom Initials")
        self.resize(740, 740)
        self.stop_over_time = float(stop_over_time)
        self.door_opening_time = float(door_opening_time)
        self.velocity_fps = float(velocity_fps)
        self.generated_scenario = None
        self.worker = None

        root = QVBoxLayout(self)
        explanation = QLabel(
            "HC optimum hit rate (%) — lower means harder for this HC protocol. "
            "Success means reaching the completed exact subset-DP optimum "
            "(absolute tolerance 1e-9 s, relative tolerance 0). "
            "Capacity is unlimited. Preset bands are user targets, not "
            "recalibrated difficulty classes.")
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        files_box = QGroupBox("Files")
        files = QFormLayout(files_box)
        self.reference_edit = QLineEdit(os.path.abspath(default_reference))
        self.output_edit = QLineEdit(self._default_output(default_reference))
        self.reference_row = self._path_row(
            self.reference_edit, self._browse_reference)
        self.output_row = self._path_row(
            self.output_edit, self._browse_output)
        files.addRow("Reference initials workbook", self.reference_row)
        files.addRow("Generated workbook", self.output_row)
        root.addWidget(files_box)

        target_box = QGroupBox("Target difficulty")
        target = QFormLayout(target_box)
        self.level_combo = QComboBox()
        for label, band in self.LEVELS:
            self.level_combo.addItem(label, band)
        self.low_spin = self._percent_spin(3.0)
        self.high_spin = self._percent_spin(10.0)
        band_row = QWidget()
        band_layout = QHBoxLayout(band_row)
        band_layout.setContentsMargins(0, 0, 0, 0)
        band_layout.addWidget(self.low_spin)
        band_layout.addWidget(QLabel("to"))
        band_layout.addWidget(self.high_spin)
        band_layout.addStretch()
        target.addRow("Difficulty level", self.level_combo)
        target.addRow("HC optimum hit-rate band (%)", band_row)
        root.addWidget(target_box)

        effort_box = QGroupBox("Search effort")
        effort = QFormLayout(effort_box)
        self.tries_spin = self._integer_spin(1, 10000, 60)
        self.screen_spin = self._integer_spin(0, 100000, 150)
        self.confirm_spin = self._integer_spin(1, 100000, HC_DEFAULT_RESTARTS)
        self.confirm_spin.setToolTip(
            f"Independent HC starts; at most {HC_MAX_SWEEPS} full sweeps per start. "
            "Stops earlier when a full sweep finds no improvement.")
        self.seed_spin = self._integer_spin(0, 2_000_000_000, 20260901)
        effort.addRow("Maximum candidate attempts", self.tries_spin)
        effort.addRow("Batch-best screening restarts (0 = off)", self.screen_spin)
        effort.addRow("Exact-reference selection restarts", self.confirm_spin)
        effort.addRow("First candidate seed", self.seed_spin)
        self.screen_seed_spin = self._integer_spin(0, 2_000_000_000, 11)
        self.selection_seed_spin = self._integer_spin(0, 2_000_000_000, 12)
        self.holdout_seed_spin = self._integer_spin(0, 2_000_000_000, 13)
        seed_row = QHBoxLayout()
        for label, spin in (("Screen", self.screen_seed_spin),
                            ("Selection", self.selection_seed_spin),
                            ("Later holdout", self.holdout_seed_spin)):
            seed_row.addWidget(QLabel(label))
            seed_row.addWidget(spin)
        effort.addRow("Distinct HC seeds", seed_row)
        self.exact_calls_spin = self._integer_spin(1, 30, 16)
        self.exact_seconds_spin = QDoubleSpinBox()
        self.exact_seconds_spin.setRange(0.001, 86400)
        self.exact_seconds_spin.setDecimals(3)
        self.exact_seconds_spin.setValue(120)
        self.exact_seconds_spin.setSuffix(" s")
        effort.addRow("Exact solver maximum calls", self.exact_calls_spin)
        effort.addRow("Exact solver time limit per candidate", self.exact_seconds_spin)
        root.addWidget(effort_box)

        settings = QLabel(
            f"Fixed objective: Python objFunDestination / WT (estimated mean "
            f"waiting time to pickup opening start). Independent of dispatch/objective selections. "
            f"Building & Car settings: "
            f"stop-over time {self.stop_over_time:g} s, "
            f"door opening {self.door_opening_time:g} s (included in stop-over, not added at pickup), "
            f"velocity {self.velocity_fps:g} floors/s. The generated "
            "workbook preserves the reference problem structure. "
            "Selection is not holdout validation; the reserved holdout seed "
            "is only used in a later evaluation. Incomplete DP saves no scenario.")
        settings.setWordWrap(True)
        settings.setStyleSheet("color: #666;")
        root.addWidget(settings)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.progress_bar)
        root.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.create_button = self.buttons.button(QDialogButtonBox.Save)
        self.create_button.setText("Create scenario")
        self.cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._start_generation)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.level_combo.currentIndexChanged.connect(self._level_changed)
        self.low_spin.valueChanged.connect(self._validate_band)
        self.high_spin.valueChanged.connect(self._validate_band)
        self._level_changed(0)

    @staticmethod
    def _default_output(reference: str) -> str:
        directory = os.path.dirname(os.path.abspath(reference))
        return os.path.join(directory, "custom_initials_hard.xlsx")

    @staticmethod
    def _path_row(line_edit: QLineEdit, callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        button = QPushButton("Browse…")
        button.clicked.connect(callback)
        layout.addWidget(button)
        return row

    @staticmethod
    def _percent_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.setSuffix(" %")
        return spin

    @staticmethod
    def _integer_spin(low: int, high: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        return spin

    def _browse_reference(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reference initials workbook",
            self.reference_edit.text(), "Excel files (*.xlsx)")
        if path:
            self.reference_edit.setText(path)
            if not self.output_edit.text():
                self.output_edit.setText(self._default_output(path))

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save generated initials workbook",
            self.output_edit.text(), "Excel files (*.xlsx)")
        if path:
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.output_edit.setText(path)

    def _level_changed(self, index: int):
        band = self.level_combo.itemData(index)
        custom = band is None
        if not custom:
            self.low_spin.setValue(float(band[0]))
            self.high_spin.setValue(float(band[1]))
            slug = ("hard" if index == 0 else
                    "intermediate" if index == 1 else "easy")
            reference = self.reference_edit.text()
            self.output_edit.setText(os.path.join(
                os.path.dirname(os.path.abspath(reference)),
                f"custom_initials_{slug}.xlsx"))
        self.low_spin.setEnabled(custom)
        self.high_spin.setEnabled(custom)
        self._validate_band()

    def _validate_band(self):
        valid = self.low_spin.value() <= self.high_spin.value()
        self.create_button.setEnabled(valid and self.worker is None)
        return valid

    def _start_generation(self):
        reference_text = self.reference_edit.text().strip()
        output_text = self.output_edit.text().strip()
        reference = os.path.abspath(reference_text) if reference_text else ""
        output = os.path.abspath(output_text) if output_text else ""
        if not os.path.isfile(reference):
            QMessageBox.warning(self, "Create scenario",
                                "Select an existing reference .xlsx file.")
            return
        if not output:
            QMessageBox.warning(self, "Create scenario",
                                "Select an output .xlsx file.")
            return
        if not output.lower().endswith(".xlsx"):
            output += ".xlsx"
            self.output_edit.setText(output)
        if reference == output:
            QMessageBox.warning(
                self, "Create scenario",
                "The generated file must not overwrite the reference file.")
            return
        if os.path.exists(output):
            answer = QMessageBox.question(
                self, "Replace generated workbook?",
                f"The output file already exists:\n{output}\n\nReplace it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        if not self._validate_band():
            QMessageBox.warning(
                self, "Create scenario",
                "The lower success limit must not exceed the upper limit.")
            return

        arguments = {
            "reference_path": reference,
            "output_path": output,
            "target_low": self.low_spin.value(),
            "target_high": self.high_spin.value(),
            "stop_over_time": self.stop_over_time,
            "door_opening_time": self.door_opening_time,
            "velocity_fps": self.velocity_fps,
            "tries": self.tries_spin.value(),
            "screen_restarts": self.screen_spin.value(),
            "confirm_restarts": self.confirm_spin.value(),
            "seed0": self.seed_spin.value(),
            "screen_seed": self.screen_seed_spin.value(),
            "selection_seed": self.selection_seed_spin.value(),
            "holdout_seed": self.holdout_seed_spin.value(),
            "exact_max_calls": self.exact_calls_spin.value(),
            "exact_time_limit": self.exact_seconds_spin.value(),
        }
        self.worker = ScenarioGenerationWorker(arguments, self)
        self.worker.progress.connect(self._show_progress)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.cancelled.connect(self._cancelled)
        self.progress_bar.setRange(0, self.tries_spin.value())
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting scenario search…")
        self._set_inputs_enabled(False)
        self.cancel_button.setText("Cancel search")
        self.worker.start()

    def _set_inputs_enabled(self, enabled: bool):
        for widget in (self.reference_edit, self.output_edit,
                       self.reference_row, self.output_row,
                       self.level_combo, self.tries_spin, self.screen_spin,
                       self.confirm_spin, self.seed_spin, self.screen_seed_spin,
                       self.selection_seed_spin, self.holdout_seed_spin,
                       self.exact_calls_spin, self.exact_seconds_spin):
            widget.setEnabled(enabled)
        custom = self.level_combo.currentData() is None
        self.low_spin.setEnabled(enabled and custom)
        self.high_spin.setEnabled(enabled and custom)
        self.create_button.setEnabled(enabled)

    def _show_progress(self, attempt: int, total: int, stage: str,
                       score: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(attempt)
        suffix = f" — hit rate {score}" if score else ""
        self.status_label.setText(
            f"Candidate {attempt}/{total}: {stage}{suffix}")

    def _completed(self, result):
        self.generated_scenario = result
        self.worker.wait()
        self.worker = None
        self.status_label.setText(
            f"Created {result.path} — HC optimum hit rate "
            f"{result.difficulty:.1f}%.")
        super().accept()

    def _failed(self, message: str):
        self.worker.wait()
        self.worker = None
        self._set_inputs_enabled(True)
        self.cancel_button.setText("Cancel")
        self.cancel_button.setEnabled(True)
        self._validate_band()
        QMessageBox.warning(self, "Scenario creation failed", message)

    def _cancelled(self):
        self.worker.wait()
        self.worker = None
        super().reject()

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelling after the current step…")
            return
        super().reject()
