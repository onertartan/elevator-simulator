"""[A8] A passenger accepted into a door cycle that was already opening or open
stops waiting at the acceptance, not at the earlier opening start.

Real Car / Controller, 1 s ticks (the _World helper of
test_pending_board_direction). The car carries p: 3 -> 5 and reaches floor 5
at t = 13, where its doors start to open. A group g: 5 -> 3 waits at floor 5
from t = 0. g becomes boardable for this car only at tau, either because g is
assigned to the car at tau (case 1) or because the car's work ahead is given
to another car at tau, so the car turns at floor 5 (case 2). Before [A8] the
engine ended g's wait at 13 for every tau in 14..17; the boarding and arrival
times were and are unaffected (RUNNING.md section 15).

    python tests/test_wt_midcycle_acceptance.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_structures.hall_call import HallCall           # noqa: E402
from data_structures.passenger import Passenger          # noqa: E402
from test_pending_board_direction import _World          # noqa: E402

DOORS_START_OPENING = 13          # car reaches floor 5 at t = 13


def _waiting_group(w, floor, DF, car_id):
    """A passenger waiting since t = 0, with its hall call, assigned to car_id."""
    q = Passenger(float(floor), 0.0, float(DF))
    q.carId = car_id
    w.P.add(q)
    h = HallCall(float(floor), 0.0, q.direction)
    h.carId = car_id
    w.HC.add(h)
    return q, h


def _refresh(w):
    w.dm.update_car_service_lists([w.car], w.HC, w.P)
    w.ctrl.updateCarStatesForNextDecision([w.car])


def run_case1(tau):
    """g belongs to another car (id 2) until tau, then to this car."""
    w = _World(start_floor=2.0)
    p = w.assign(3, 5)
    g, hg = _waiting_group(w, 5, 3, car_id=2)
    _refresh(w)
    while w.t < 80 and g.DAT is None:
        if w.t == tau:
            g.carId = hg.carId = 1
            _refresh(w)
        w.tick()
    return p, g


def run_case2(tau):
    """g belongs to this car from the start but goes down; the car keeps going
    up for h: 8 -> 9 until h is given to another car at tau."""
    w = _World(start_floor=2.0)
    p = w.assign(3, 5)
    g, _ = _waiting_group(w, 5, 3, car_id=1)
    h, hh = _waiting_group(w, 8, 9, car_id=1)
    _refresh(w)
    while w.t < 80 and g.DAT is None:
        if w.t == tau:
            h.carId = hh.carId = 2
            _refresh(w)
        w.tick()
    return p, g


class MidCycleAcceptanceTests(unittest.TestCase):

    def check(self, g, wait_ends, boards):
        self.assertEqual(g.doorOpeningStartTime, DOORS_START_OPENING
                         if wait_ends < DOORS_START_OPENING + 5 else wait_ends)
        self.assertEqual(g.pickupStartTime, wait_ends)
        self.assertEqual(g.WT, wait_ends)                      # QJT = 0
        self.assertEqual(g.BT, boards)
        self.assertEqual(g.WT + g.TrT, g.TTD)

    def test_case1_assigned_while_doors_open(self):
        # tau: (end of wait, boarding); boarding = acceptance + 2 s (counter restart)
        expected = {0: (13, 15), 13: (13, 15), 15: (15, 17), 17: (17, 19), 18: (18, 20)}
        for tau, (wait_ends, boards) in expected.items():
            with self.subTest(tau=tau):
                p, g = run_case1(tau)
                self.assertEqual(p.DAT, DOORS_START_OPENING)
                self.check(g, wait_ends, boards)

    def test_case2_car_turns_while_doors_open(self):
        expected = {13: (13, 15), 14: (14, 16), 15: (15, 17), 16: (16, 18), 17: (17, 19), 18: (18, 20)}
        for tau, (wait_ends, boards) in expected.items():
            with self.subTest(tau=tau):
                p, g = run_case2(tau)
                self.assertEqual(p.DAT, DOORS_START_OPENING)
                self.check(g, wait_ends, boards)

    def test_wait_never_ends_before_the_group_is_boardable(self):
        for run in (run_case1, run_case2):
            for tau in range(13, 18):
                with self.subTest(case=run.__name__, tau=tau):
                    _, g = run(tau)
                    self.assertGreaterEqual(g.QJT + g.WT, tau)


if __name__ == "__main__":
    unittest.main()
