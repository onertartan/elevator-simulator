"""Offscreen display contract for the two passenger waiting measures."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists
from gui.tabs.display_tab import DisplayTab, RESULT_ROWS
from simulator import Simulator

app = QApplication.instance() or QApplication([])


class WaitingMetricsDisplayTests(unittest.TestCase):
    def test_primary_and_secondary_render_with_distinct_labels(self):
        HC, P = HallCallLists(), PassengerLists()
        served = Passenger(3, 0, 5)
        served.start_pickup(3)
        served.board(1, 5)
        served.alight(8)
        P.served[1].append(served)
        pending = Passenger(3, 1, 6)
        pending.start_pickup(3)
        pending.advance_waiting_time(4)
        P.add(pending)
        sim = object.__new__(Simulator)
        sim.dataType = 1
        results = sim.fillResultsTable(HC, P, [NS(tripTime=4, numOfServedPassengers=1)])
        view = DisplayTab()
        try:
            view.render_frame({"tables": {
                "car": {"columns": [], "rows": [], "data": []},
                "passengers": sim.fillPassengerTables(P), "results": results}})
            self.assertEqual(view.results_table.rowCount(), 10)
            self.assertEqual(len(results), len(RESULT_ROWS))
            self.assertIn("opening start", view.results_table.verticalHeaderItem(6).text())
            self.assertEqual(view.results_table.item(6, 0).text(), "3.00")
            self.assertIn("boarding", view.results_table.verticalHeaderItem(9).text())
            self.assertEqual(view.results_table.item(9, 0).text(), "5.00")
            self.assertEqual(view.passenger_up_table.item(3, 0).text(), "2")
            self.assertEqual(view.passenger_up_table.item(5, 0).text(), "3")
        finally:
            view.close()

    def test_custom_initial_cabin_passengers_excluded_from_both_measures(self):
        HC, P = HallCallLists(), PassengerLists()
        cabin = Passenger(3, -1, 5)
        cabin.board(1, -1)
        cabin.alight(20)
        ordinary = Passenger(3, 0, 5)
        ordinary.start_pickup(3)
        ordinary.board(1, 5)
        ordinary.alight(20)
        P.served[1].extend([cabin, ordinary])
        sim = object.__new__(Simulator)
        sim.dataType = 3
        results = sim.fillResultsTable(HC, P, [NS(tripTime=4, numOfServedPassengers=2)])
        self.assertEqual((results[1], results[3], results[6]), ("3", "1", "3.00"))
        self.assertEqual(results[8:], ["5", "5.00"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
