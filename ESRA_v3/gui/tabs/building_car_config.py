"""
gui/tabs/building_car_config.py
================================
Tab 1: 'Building Configuration & Car Configuration'.
Faithful port of the MATLAB source:

  * Both the range slider and the fixed slider are always enabled.
  * Lamps are indicators: the last-touched slider's lamp turns green
    (swapLamps in the MATLAB code).
  * Moving the FIXED slider also snaps the range slider to [v, v],
    updates the min/max labels, and resets Step Size to '1'
    (setRangeSlider + the ...SliderFixedValueChanged callbacks).
  * Start data reads min/max from the labels — so whichever slider was
    touched last defines the effective values.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox
)

from ..widgets.range_slider import RangeSlider, TickSlider
from ..widgets.lamp import Lamp, swap_lamps


class RangedParameterBox(QGroupBox):
    """'Number of floors' / 'Number of cars' panel."""

    def __init__(self, noun, minimum, maximum, default_value, ticks, parent=None):
        super().__init__(f"Number of {noun}", parent)
        self.noun = noun

        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        # ---- Ranged row ------------------------------------------------
        ranged_row = QHBoxLayout()
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(f"Range of numbers of {noun}"))
        self.lamp_range = Lamp(on=False)
        left_col.addWidget(self.lamp_range)
        left_col.addStretch()

        # MATLAB default: Value = [default, default]
        self.range_slider = RangeSlider(minimum, maximum,
                                        default_value, default_value,
                                        step=1, major_ticks=ticks)
        ranged_row.addLayout(left_col)
        ranged_row.addWidget(self.range_slider, 1)
        outer.addLayout(ranged_row)

        # Step size + min/max readout
        readout_row = QHBoxLayout()
        readout_row.addWidget(QLabel("Step Size"))
        self.step_combo = QComboBox()
        self.step_combo.addItems([str(i) for i in range(1, 31)])  # '1'..'30'
        self.step_combo.setFixedWidth(70)
        readout_row.addWidget(self.step_combo)
        readout_row.addSpacing(30)
        readout_row.addWidget(QLabel(f"Minimum number of {noun} :"))
        self.min_value = QLabel(str(default_value))
        readout_row.addWidget(self.min_value)
        readout_row.addSpacing(20)
        readout_row.addWidget(QLabel(f"Maximum number of {noun} :"))
        self.max_value = QLabel(str(default_value))
        readout_row.addWidget(self.max_value)
        readout_row.addStretch()
        outer.addLayout(readout_row)

        # ---- Fixed row ---------------------------------------------------
        self.fixed_title = QLabel(f"Fixed number of {noun} : {default_value}")
        outer.addWidget(self.fixed_title)

        fixed_row = QHBoxLayout()
        fixed_col = QVBoxLayout()
        self.lamp_fixed = Lamp(on=True)  # green by default, as in screenshot
        fixed_col.addWidget(self.lamp_fixed)
        fixed_col.addStretch()
        self.fixed_slider = TickSlider(minimum, maximum, default_value,
                                       major_ticks=ticks)
        fixed_row.addLayout(fixed_col)
        fixed_row.addWidget(self.fixed_slider, 1)
        outer.addLayout(fixed_row)

        # ---- wiring (ports of the ValueChanged callbacks) ------------------
        self.range_slider.rangeEdited.connect(self._range_slider_changed)
        self.fixed_slider.sliderReleased.connect(self._fixed_slider_changed)
        self.fixed_slider.valueChanged.connect(
            lambda v: self.fixed_title.setText(f"Fixed number of {noun} : {v}"))
        self.step_combo.currentTextChanged.connect(
            lambda t: self.range_slider.setStep(int(t)))

    def _range_slider_changed(self, low, high):
        # floorsSliderRangeValueChanged / carsSliderRangeValueChanged
        self.min_value.setText(str(low))
        self.max_value.setText(str(high))
        swap_lamps(self.lamp_range, self.lamp_fixed)

    def _fixed_slider_changed(self):
        # floorsSliderFixedValueChanged / carsSliderFixedValueChanged:
        # sync range slider to [v, v], update all labels, reset step size
        v = self.fixed_slider.value()
        self.range_slider.setLow(v)
        self.range_slider.setHigh(v)
        self.min_value.setText(str(v))
        self.max_value.setText(str(v))
        self.fixed_title.setText(f"Fixed number of {self.noun} : {v}")
        swap_lamps(self.lamp_fixed, self.lamp_range)
        self.step_combo.setCurrentText("1")

    # ---- accessors ------------------------------------------------------
    def effective_min(self):
        return int(self.min_value.text())

    def effective_max(self):
        return int(self.max_value.text())

    def step(self):
        return int(self.step_combo.currentText())

    def to_state(self):
        return {
            "range": [self.range_slider.low(), self.range_slider.high()],
            "fixed": self.fixed_slider.value(),
            "step": self.step_combo.currentText(),
            "min_label": self.min_value.text(),
            "max_label": self.max_value.text(),
            "lamp_fixed_on": self.lamp_fixed.is_on(),
        }

    def from_state(self, s):
        self.range_slider.setLow(s["range"][0])
        self.range_slider.setHigh(s["range"][1])
        self.fixed_slider.setValue(s["fixed"])
        self.step_combo.setCurrentText(s["step"])
        self.min_value.setText(s["min_label"])
        self.max_value.setText(s["max_label"])
        self.lamp_fixed.set_on(s["lamp_fixed_on"])
        self.lamp_range.set_on(not s["lamp_fixed_on"])


class BuildingCarConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Floor height — Limits [2 5], default 3
        height_row = QHBoxLayout()
        height_row.addWidget(QLabel("Floor height"))
        self.floor_height = QDoubleSpinBox()
        self.floor_height.setRange(2.0, 5.0)
        self.floor_height.setSingleStep(0.1)
        self.floor_height.setValue(3.0)
        self.floor_height.setFixedWidth(90)
        height_row.addWidget(self.floor_height)
        height_row.addStretch()
        layout.addLayout(height_row)

        floor_ticks = [3, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
        car_ticks = list(range(2, 11))
        self.floors_box = RangedParameterBox("floors", 3, 50, 20, floor_ticks)
        self.cars_box = RangedParameterBox("cars", 2, 10, 5, car_ticks)
        layout.addWidget(self.floors_box)
        layout.addWidget(self.cars_box)

        # Bottom grid — limits/defaults straight from the MATLAB source
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

        def dspin(minimum, maximum, value, step=1.0, decimals=2):
            b = QDoubleSpinBox()
            b.setRange(minimum, maximum)
            b.setDecimals(decimals)
            b.setSingleStep(step)
            b.setValue(value)
            b.setFixedWidth(90)
            return b

        def ispin(minimum, maximum, value):
            b = QSpinBox()
            b.setRange(minimum, maximum)
            b.setValue(value)
            b.setFixedWidth(90)
            return b

        self.car_capacity = ispin(0, 50, 10)                     # Limits [0 50]
        self.car_velocity = dspin(0.1, 20.0, 1.5, step=0.1)      # Limits [0.1 20]
        self.car_capacity_factor = dspin(0.0, 1.0, 1.0, step=0.05)  # Limits [0 1]
        self.door_opening_time = ispin(0, 10, 2)                 # Limits [0 10]
        self.door_closing_time = ispin(0, 10, 2)                 # Limits [0 10]
        self.passenger_transfer_time = ispin(0, 10, 3)           # Limits [0 10]

        self.parking_method = QComboBox()
        self.parking_method.addItems(
            ["Park1 (No parking method)", "Park2", "Park3", "Park4"])
        self.parking_method.setFixedWidth(200)

        grid.addWidget(QLabel("Car Capacity"), 0, 0)
        grid.addWidget(self.car_capacity, 0, 1)
        grid.addWidget(QLabel("Door opening time"), 0, 2)
        grid.addWidget(self.door_opening_time, 0, 3)
        grid.addWidget(QLabel("Parking Method"), 0, 4)
        grid.addWidget(self.parking_method, 0, 5)
        grid.addWidget(QLabel("Car velocity"), 1, 0)
        grid.addWidget(self.car_velocity, 1, 1)
        grid.addWidget(QLabel("Door closing time"), 1, 2)
        grid.addWidget(self.door_closing_time, 1, 3)
        grid.addWidget(QLabel("Car capacity factor"), 2, 0)
        grid.addWidget(self.car_capacity_factor, 2, 1)
        grid.addWidget(QLabel("Passenger transfer time"), 2, 2)
        grid.addWidget(self.passenger_transfer_time, 2, 3)
        grid.setColumnStretch(6, 1)
        layout.addLayout(grid)
        layout.addStretch()

    # ---- startData contribution (mirrors buttonStartButtonPushed) ------
    def to_start_data(self):
        return {
            "NFmin": self.floors_box.effective_min(),
            "NFmax": self.floors_box.effective_max(),
            "NFstep": self.floors_box.step(),
            "floorHeight": self.floor_height.value(),
            "NCmin": self.cars_box.effective_min(),
            "NCmax": self.cars_box.effective_max(),
            "parkingAlgorithm": self.parking_method.currentText(),
            "doorOpeningTime": self.door_opening_time.value(),
            "doorClosingTime": self.door_closing_time.value(),
            "passengerTransferTime": self.passenger_transfer_time.value(),
            "carCapacity": self.car_capacity.value(),
            "carVelocity": self.car_velocity.value(),
            "carCapacityFactor": self.car_capacity_factor.value(),
        }

    def to_state(self):
        return {
            "floor_height": self.floor_height.value(),
            "floors": self.floors_box.to_state(),
            "cars": self.cars_box.to_state(),
            "car_capacity": self.car_capacity.value(),
            "car_velocity": self.car_velocity.value(),
            "car_capacity_factor": self.car_capacity_factor.value(),
            "door_opening_time": self.door_opening_time.value(),
            "door_closing_time": self.door_closing_time.value(),
            "passenger_transfer_time": self.passenger_transfer_time.value(),
            "parking_method": self.parking_method.currentText(),
        }

    def from_state(self, s):
        self.floor_height.setValue(s["floor_height"])
        self.floors_box.from_state(s["floors"])
        self.cars_box.from_state(s["cars"])
        self.car_capacity.setValue(s["car_capacity"])
        self.car_velocity.setValue(s["car_velocity"])
        self.car_capacity_factor.setValue(s["car_capacity_factor"])
        self.door_opening_time.setValue(s["door_opening_time"])
        self.door_closing_time.setValue(s["door_closing_time"])
        self.passenger_transfer_time.setValue(s["passenger_transfer_time"])
        self.parking_method.setCurrentText(s["parking_method"])
