"""
gui/tabs/display_tab.py
========================
Tab 5: 'Display Tab'. Ported from the MATLAB source:

  * Checkboxes: 'Display traffic flow' (default on),
                'Display tabular data' (default on).
  * 'Display speed' slider, Limits [1 5], default 3.
  * Traffic-flow plot area (pyqtgraph TrafficFlowView).
  * Tables with the exact row/column headers from the source:
      - carTable          (4 unnamed columns)
      - passengerUpTable  ('Waiting up passengers')
      - passengerDownTable('Waiting down passengers')
      - resultsTable      (8 named result rows)
      - countersTable     (6 named counter rows, see [L2])

Layout fixes 2026-07-17 ([L1]-[L3]):
  [L1] The flow view no longer shares a horizontal band with the
       tables. New layout: controls on top, then a horizontal split -
       the animation on the left (takes all remaining width/height)
       and ALL tables piled vertically in a fixed-width column on the
       right. Together with flow_view [V1] (locked 1:1 aspect) the
       building keeps square cells and centres in the left region
       instead of stretching across the window.
  [L2] The counters table is transposed: 1 row x 6 named columns in
       MATLAB -> 6 named rows x 1 column, so it fits the right-hand
       pile. render_frame fills it vertically to match.
  [L3] Table pile stretch: passenger tables grow (their column count
       varies with waiting passengers), results/counters stay compact.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QTableWidget, QSizePolicy, QTableWidgetItem
)
from ..flow_view import TrafficFlowView

RESULT_ROWS = [
    "Total car trip time", "Total passenger waiting time",
    "Total hall call waiting time", "Number of served passengers",
    "Number of responded hall calls", "Average car trip time",
    "Average passenger waiting time", "Average hall call waiting time",
]
COUNTER_ROWS = [                                    # [L2] rows, not columns
    "Building Conf.", "Car Conf.", "Traffic Conf.",
    "Sim counter/ Max sims.", "Total Run/ Max Run", "Total runtime",
]

_SIDE_PANEL_WIDTH = 420                             # [L1]


def _table(rows, cols, row_labels=None, col_labels=None):
    t = QTableWidget(rows, cols)
    if row_labels:
        t.setVerticalHeaderLabels(row_labels)
    else:
        t.verticalHeader().setVisible(False)
    if col_labels:
        t.setHorizontalHeaderLabels(col_labels)
    else:
        t.horizontalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    return t


class DisplayTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- top controls ---------------------------------------------------
        controls = QHBoxLayout()
        self.display_traffic_flow = QCheckBox("Display traffic flow")
        self.display_traffic_flow.setChecked(True)
        self.display_tabular_data = QCheckBox("Display tabular data")
        self.display_tabular_data.setChecked(True)
        self.sprite_graphics = QCheckBox("Sprite graphics")
        self.sprite_graphics.setChecked(True)
        controls.addWidget(self.display_traffic_flow)
        controls.addWidget(self.display_tabular_data)
        controls.addWidget(self.sprite_graphics)
        controls.addSpacing(30)
        controls.addWidget(QLabel("Display speed"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 5)
        self.speed_slider.setValue(3)
        self.speed_slider.setFixedWidth(160)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(1)
        controls.addWidget(self.speed_slider)
        controls.addStretch()
        layout.addLayout(controls)

        # ---- main split: animation left, table pile right [L1] -----------
        split = QHBoxLayout()
        split.setSpacing(10)

        self.flow_view = TrafficFlowView()
        self.flow_view.setMinimumHeight(260)
        self.flow_view.setSizePolicy(QSizePolicy.Expanding,
                                     QSizePolicy.Expanding)
        split.addWidget(self.flow_view, 1)

        side = QVBoxLayout()
        side.setSpacing(6)
        self.car_table = _table(0, 4)
        self.passenger_up_table = _table(0, 1)
        self.passenger_down_table = _table(0, 1)
        self.results_table = _table(len(RESULT_ROWS), 1,
                                    row_labels=RESULT_ROWS)
        self.counters_table = _table(len(COUNTER_ROWS), 1,       # [L2]
                                     row_labels=COUNTER_ROWS)

        for title, widget, stretch in (            # [L3]
                ("Cars", self.car_table, 2),
                ("Waiting up passengers", self.passenger_up_table, 2),
                ("Waiting down passengers", self.passenger_down_table, 2),
                ("Results", self.results_table, 3),
                ("Counters", self.counters_table, 2)):
            side.addWidget(QLabel(title))
            side.addWidget(widget, stretch)

        side_panel = QWidget()
        side_panel.setLayout(side)
        side_panel.setFixedWidth(_SIDE_PANEL_WIDTH)
        split.addWidget(side_panel, 0)
        self._side_panel = side_panel

        layout.addLayout(split, 1)

        # ---- wiring (checkbox callbacks) --------------------------------
        self.display_traffic_flow.toggled.connect(self.flow_view.setVisible)
        self.sprite_graphics.toggled.connect(self.flow_view.set_use_sprites)
        self.display_tabular_data.toggled.connect(self._toggle_tables)

    def _toggle_tables(self, visible):
        # displayTabularDataCheckBoxValueChanged: toggle + clear
        for t in (self.car_table, self.passenger_up_table,
                  self.passenger_down_table):
            t.setVisible(visible)
            t.setRowCount(0)

    def render_frame(self, frame):
        """GUI-thread slot for Simulator frames (worker.frame signal).
        Updates the flow animation, the four data tables, and counters."""
        self.flow_view.render_frame(frame)

        tables = frame.get("tables")
        if tables:
            self._fill(self.car_table, tables["car"])
            self._fill(self.passenger_up_table, tables["passengers"][1])
            self._fill(self.passenger_down_table, tables["passengers"][2])
            for r, value in enumerate(tables["results"]):
                self.results_table.setItem(r, 0, QTableWidgetItem(value))

        for r, value in enumerate(frame.get("counters", [])):    # [L2]
            self.counters_table.setItem(r, 0, QTableWidgetItem(value))

    @staticmethod
    def _fill(table, spec):
        """Fill a QTableWidget from a {'columns','rows','data'} frame spec."""
        cols, rows, data = spec["columns"], spec["rows"], spec["data"]
        table.setColumnCount(len(cols))
        table.setRowCount(len(rows))
        table.setHorizontalHeaderLabels(cols)
        table.setVerticalHeaderLabels(rows)
        table.horizontalHeader().setVisible(bool(cols))
        table.verticalHeader().setVisible(bool(rows))
        for r, row in enumerate(data):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))

    def clear_all(self):
        """Port of the clearing done in terminateButtonPushed."""
        self.car_table.setRowCount(0)
        self.passenger_up_table.setRowCount(0)
        self.passenger_down_table.setRowCount(0)
        for r in range(self.results_table.rowCount()):
            item = self.results_table.item(r, 0)
            if item:
                item.setText("")

    def to_start_data(self):
        return {
            "displayTrafficFlow": self.display_traffic_flow.isChecked(),
            "displayTabularData": self.display_tabular_data.isChecked(),
            "displaySpeed": self.speed_slider.value(),
        }

    def to_state(self):
        return {
            "display_traffic_flow": self.display_traffic_flow.isChecked(),
            "display_tabular_data": self.display_tabular_data.isChecked(),
            "speed": self.speed_slider.value(),
        }

    def from_state(self, s):
        self.display_traffic_flow.setChecked(s["display_traffic_flow"])
        self.display_tabular_data.setChecked(s["display_tabular_data"])
        self.speed_slider.setValue(s["speed"])