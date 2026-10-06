"""
gui/tabs/traffic_config.py
===========================
Tab 2: 'Traffic Configuration'. Ported from the MATLAB source:

  * Traffic Components Configuration panel with two sub-panels:
      - Interval (range) panel: Incoming & Interfloor RangeSliders 0-100
        with min/max readout labels (defaults 0 / 100), trafficLampRange.
      - Fixed panel: Fixed incoming (30), Interfloor (40), Outgoing (30)
        single sliders, trafficLampFixed (green by default).
    Touching a slider in one panel turns that panel's lamp green.
  * Passenger Arrival button group:
      - 'No new passenger' (default)
      - 'Passenger Arrival Rate (seconds/passenger)' + spinner (>=0.1, 10)

NOTE (from buttonStartButtonPushed): the MATLAB app currently reads
INCmin/INCmax and INTmin/INTmax from the *fixed* sliders only (the
range-slider lines are commented out in the source), and validates
INCmin + INTmin <= 100 at start. We keep both behaviours and expose
both sets of values.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QDoubleSpinBox, QRadioButton, QButtonGroup
)

from ..widgets.range_slider import RangeSlider, TickSlider
from ..widgets.lamp import Lamp, swap_lamps

PCT_TICKS = list(range(0, 101, 10))  # MajorTicks = [0 10 ... 100]


class TrafficConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        components_box = QGroupBox("Traffic Components Configuration")
        components_layout = QVBoxLayout(components_box)

        # ---- Interval (range) panel ---------------------------------------
        interval_panel = QGroupBox()
        ip = QVBoxLayout(interval_panel)
        self.lamp_range = Lamp(on=False)

        inc_row = QHBoxLayout()
        inc_row.addWidget(QLabel("Incoming traffic"))
        self.incoming_range = RangeSlider(0, 100, 0, 100, step=1,
                                          major_ticks=PCT_TICKS)
        inc_row.addWidget(self.incoming_range, 1)
        ip.addLayout(inc_row)

        inc_readout = QHBoxLayout()
        inc_readout.addWidget(QLabel("Minimum incoming traffic:"))
        self.incoming_min = QLabel("0")
        inc_readout.addWidget(self.incoming_min)
        inc_readout.addSpacing(20)
        inc_readout.addWidget(QLabel("Maximum incoming traffic:"))
        self.incoming_max = QLabel("100")
        inc_readout.addWidget(self.incoming_max)
        inc_readout.addStretch()
        ip.addLayout(inc_readout)

        int_row = QHBoxLayout()
        int_row.addWidget(QLabel("Interfloor traffic"))
        self.interfloor_range = RangeSlider(0, 100, 0, 100, step=1,
                                            major_ticks=PCT_TICKS)
        int_row.addWidget(self.interfloor_range, 1)
        ip.addLayout(int_row)

        int_readout = QHBoxLayout()
        int_readout.addWidget(QLabel("Minimum interfloor traffic:"))
        self.interfloor_min = QLabel("0")
        int_readout.addWidget(self.interfloor_min)
        int_readout.addSpacing(20)
        int_readout.addWidget(QLabel("Maximum interfloor traffic:"))
        self.interfloor_max = QLabel("100")
        int_readout.addWidget(self.interfloor_max)
        int_readout.addStretch()
        int_readout.addWidget(self.lamp_range)
        ip.addLayout(int_readout)

        components_layout.addWidget(interval_panel)

        # ---- Fixed panel ---------------------------------------------------
        fixed_panel = QGroupBox()
        fp = QGridLayout(fixed_panel)
        self.lamp_fixed = Lamp(on=True)

        self.fixed_incoming_label = QLabel("30")
        self.fixed_incoming = TickSlider(0, 100, 30, major_ticks=PCT_TICKS)
        self.fixed_interfloor_label = QLabel("40")
        self.fixed_interfloor = TickSlider(0, 100, 40, major_ticks=PCT_TICKS)
        self.fixed_outgoing_label = QLabel("30")
        self.fixed_outgoing = TickSlider(0, 100, 30, major_ticks=PCT_TICKS)

        fp.addWidget(QLabel("Fixed incoming traffic:"), 0, 0)
        fp.addWidget(self.fixed_incoming_label, 0, 1)
        fp.addWidget(self.fixed_incoming, 0, 2)
        fp.addWidget(QLabel("Interfloor traffic"), 1, 0)
        fp.addWidget(self.fixed_interfloor_label, 1, 1)
        fp.addWidget(self.fixed_interfloor, 1, 2)
        fp.addWidget(QLabel("Outgoing traffic"), 2, 0)
        fp.addWidget(self.fixed_outgoing_label, 2, 1)
        fp.addWidget(self.fixed_outgoing, 2, 2)
        fp.addWidget(self.lamp_fixed, 3, 0)
        fp.setColumnStretch(2, 1)

        components_layout.addWidget(fixed_panel)
        layout.addWidget(components_box)

        # ---- Passenger Arrival group ------------------------------------
        arrival_box = QGroupBox("Passenger Arrival")
        ab = QVBoxLayout(arrival_box)
        self.no_new_passenger_rb = QRadioButton("No new passenger")
        self.no_new_passenger_rb.setChecked(True)   # default in MATLAB
        self.arrival_rate_rb = QRadioButton(
            "Passenger Arrival Rate (seconds/passenger)")
        self.arrival_rate_spinner = QDoubleSpinBox()
        self.arrival_rate_spinner.setRange(0.1, 1e9)  # Limits [0.1 Inf]
        self.arrival_rate_spinner.setValue(10)
        self.arrival_rate_spinner.setFixedWidth(90)

        group = QButtonGroup(self)
        group.addButton(self.no_new_passenger_rb)
        group.addButton(self.arrival_rate_rb)

        ab.addWidget(self.no_new_passenger_rb)
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.arrival_rate_rb)
        rate_row.addWidget(self.arrival_rate_spinner)
        rate_row.addStretch()
        ab.addLayout(rate_row)
        layout.addWidget(arrival_box)
        layout.addStretch()

        # ---- wiring: lamp swaps + label sync ---------------------------
        self.incoming_range.rangeEdited.connect(
            lambda lo, hi: self._range_touched(self.incoming_min,
                                               self.incoming_max, lo, hi))
        self.interfloor_range.rangeEdited.connect(
            lambda lo, hi: self._range_touched(self.interfloor_min,
                                               self.interfloor_max, lo, hi))
        for slider, label in ((self.fixed_incoming, self.fixed_incoming_label),
                              (self.fixed_interfloor, self.fixed_interfloor_label),
                              (self.fixed_outgoing, self.fixed_outgoing_label)):
            slider.valueChanged.connect(
                lambda v, lab=label: lab.setText(str(v)))
            slider.sliderReleased.connect(
                lambda: swap_lamps(self.lamp_fixed, self.lamp_range))

    def _range_touched(self, min_label, max_label, low, high):
        min_label.setText(str(low))
        max_label.setText(str(high))
        swap_lamps(self.lamp_range, self.lamp_fixed)

    # ---- startData contribution ------------------------------------------
    def to_start_data(self):
        # Mirrors the MATLAB code as written: fixed sliders feed INC/INT,
        # arrival rate is Inf unless the rate radio button is selected.
        data = {
            "INCmin": self.fixed_incoming.value(),
            "INCmax": self.fixed_incoming.value(),
            "INTmin": self.fixed_interfloor.value(),
            "INTmax": self.fixed_interfloor.value(),
            "arrivalRate": (self.arrival_rate_spinner.value()
                            if self.arrival_rate_rb.isChecked()
                            else float("inf")),
        }
        return data

    def to_state(self):
        return {
            "incoming_range": [self.incoming_range.low(), self.incoming_range.high()],
            "interfloor_range": [self.interfloor_range.low(), self.interfloor_range.high()],
            "fixed_incoming": self.fixed_incoming.value(),
            "fixed_interfloor": self.fixed_interfloor.value(),
            "fixed_outgoing": self.fixed_outgoing.value(),
            "no_new_passenger": self.no_new_passenger_rb.isChecked(),
            "arrival_rate": self.arrival_rate_spinner.value(),
            "lamp_fixed_on": self.lamp_fixed.is_on(),
        }

    def from_state(self, s):
        self.incoming_range.setLow(s["incoming_range"][0])
        self.incoming_range.setHigh(s["incoming_range"][1])
        self.interfloor_range.setLow(s["interfloor_range"][0])
        self.interfloor_range.setHigh(s["interfloor_range"][1])
        self.fixed_incoming.setValue(s["fixed_incoming"])
        self.fixed_interfloor.setValue(s["fixed_interfloor"])
        self.fixed_outgoing.setValue(s["fixed_outgoing"])
        (self.no_new_passenger_rb if s["no_new_passenger"]
         else self.arrival_rate_rb).setChecked(True)
        self.arrival_rate_spinner.setValue(s["arrival_rate"])
        self.lamp_fixed.set_on(s["lamp_fixed_on"])
        self.lamp_range.set_on(not s["lamp_fixed_on"])
