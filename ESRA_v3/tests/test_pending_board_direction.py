"""
tests/test_pending_board_direction.py
=====================================
Run from the ESRA_v3/ root:  python tests/test_pending_board_direction.py

Regression checks for [A5] (car.py, Car.updateState): the destinations of
passengers already selected for boarding (pendingBoard) count as cabin
destinations when the movement state is derived.

Real engine classes, experiment.py tick order:
    [decision]  dispatch -> update_car_service_lists -> update_car_states
    operate     checkStopOver (door cycle), move if state != 0
    update_car_states            (Controller.updateCarStatesForNextDecision)

Scenario: an empty car at 2.0 is assigned the up call of a passenger
5 -> 6 at t=0. It arrives at 5.0 at t=5, beginPickup starts the door cycle
at t=6 (counter 7), the passenger boards at t=8 (counter 5), the car
leaves at t=13. A decision is injected at t=7, inside the pre-boarding
window, assigning one more call to the same car.
"""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from car import Car
from controller import Controller
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists
from decision.decision_maker import DecisionMaker


class _DM(DecisionMaker):
    def run(self, *args):          # assignments are injected by the test
        pass


class _World:
    """One car, real lists, real controller; decisions injected by floor/DF."""

    def __init__(self, start_floor=2.0):
        self.car = Car(NS(doorOpeningTime=2, passengerTransferTime=3,
                          doorClosingTime=2, carCapacity=10,
                          carCapacityFactor=1, carVelocity=1.5,
                          floorHeight=3), 1)
        self.car.floor = self.car.previousFloor = float(start_floor)
        self.HC, self.P = HallCallLists(), PassengerLists()
        self.dm = _DM(NS(stateUpdateTypeForNextDecision="fixed"))
        self.ctrl = Controller(self.dm)
        self.clock = NS(time=0.0, Ts=1.0)
        self.t = 0

    def assign(self, floor, DF):
        """Create a waiting passenger floor -> DF and assign it (and its
        hall call) to the car, then run the decision-time state update."""
        p = Passenger(float(floor), float(self.t), float(DF))
        p.carId = 1
        self.P.add(p)
        h = HallCall(float(floor), float(self.t), p.direction)
        h.carId = 1
        self.HC.add(h)
        self.dm.update_car_service_lists([self.car], self.HC, self.P)
        self.ctrl.updateCarStatesForNextDecision([self.car])
        return p

    def tick(self):
        self.ctrl.operate([self.car], self.clock, self.HC, self.P)
        self.ctrl.updateCarStatesForNextDecision([self.car])
        self.t += 1

    def run_until(self, t_end, decisions=None):
        """Advance to tick t_end; decisions = {t: [(floor, DF), ...]}."""
        decisions = decisions or {}
        while self.t < t_end:
            for floor, DF in decisions.get(self.t, []):
                self.assign(floor, DF)
            self.tick()


class PendingBoardDirectionTests(unittest.TestCase):

    def test_baseline_trip_unchanged(self):
        """No decision in the window: timeline identical to the [A4] contract."""
        w = _World()
        w.assign(5, 6)                       # t=0
        w.run_until(6)
        self.assertEqual(w.car.floor, 5.0)
        w.tick()                             # t=6: beginPickup, counter 7 -> 6
        self.assertEqual(w.car.stopOverCounter, 6)
        self.assertEqual(w.car.state, 1)     # [A5]: was 0 before the patch
        w.run_until(9)
        self.assertEqual(w.car.load, 1)      # boarded during t=8 (counter 5)
        self.assertEqual(w.car.DF, {6.0})
        w.run_until(13)
        self.assertEqual(w.car.floor, 5.0)   # never moved during the cycle
        w.tick()                             # t=13: first move
        self.assertEqual(w.car.floor, 5.5)

    def test_down_call_on_another_floor_does_not_turn_the_car(self):
        """Down call 3 -> 1 assigned while the doors open at 5: the car keeps
        +1, delivers the 5 -> 6 passenger first, then goes down for 3."""
        w = _World()
        up = w.assign(5, 6)                  # t=0
        w.run_until(7)
        self.assertEqual(w.car.state, 1)
        w.assign(3, 1)                       # t=7: decision inside the window
        self.assertEqual(w.car.state, 1, "pending up-passenger must hold the direction")
        floors = []
        while w.t < 13:
            w.tick()
            floors.append(w.car.floor)
        self.assertTrue(all(f == 5.0 for f in floors), "no movement while the counter runs")
        self.assertEqual(w.car.state, 1)
        w.tick()                             # t=13
        self.assertEqual(w.car.floor, 5.5, "departs upwards")
        w.tick()                             # t=14: arrives at 6, cabin work done
        self.assertEqual(w.car.floor, 6.0)
        self.assertEqual(w.car.state, -1, "turns for the call below only after 6")
        w.run_until(18)                      # drop-off door-open at 6 (t=15 + 2)
        self.assertEqual(w.car.load, 0, "5 -> 6 passenger alighted at 6")
        self.assertNotIn(up, w.P.travelling[1])

    def test_down_call_on_the_same_floor_is_not_taken_in_the_same_stop(self):
        """Down call 5 -> 2 assigned while the doors open at 5 for an
        up-passenger: not boarded now, served on the way back."""
        w = _World()
        w.assign(5, 6)                       # t=0
        w.run_until(7)
        self.assertEqual(w.car.stopOverCounter, 6)
        down = w.assign(5, 2)                # t=7
        w.tick()                             # t=7 -> 8
        self.assertEqual(w.car.stopOverCounter, 5, "counter must not be restarted")
        self.assertEqual([e["p"].DF for e in w.car.pendingBoard], [6.0])
        w.tick()                             # t=8: up passenger boards
        self.assertEqual(w.car.load, 1)
        self.assertEqual(w.car.DF, {6.0})
        self.assertIn(down, w.P.waiting[2], "down passenger still waiting")
        self.assertEqual([h.floor for h in w.car.HC.waiting[2]], [5.0], "down call still assigned")
        w.run_until(13)
        w.tick()                             # t=13
        self.assertEqual(w.car.floor, 5.5, "leaves upwards with the up passenger only")
        w.tick()                             # t=14: at 6
        self.assertEqual(w.car.state, -1)
        # drop-off cycle at 6 (t=15..21), then down to 5 and pick up the down passenger
        w.run_until(24)
        self.assertEqual(w.car.floor, 5.0)
        self.assertEqual(w.car.state, -1)
        w.run_until(27)
        self.assertEqual(w.car.load, 1)
        self.assertEqual(w.car.DF, {2.0}, "down passenger boarded on the return")

    def test_up_call_on_the_same_floor_still_joins_the_stop(self):
        """Unchanged behaviour: a same-direction call at the car's floor is
        taken into the current stop (counter restarts, both board)."""
        w = _World()
        w.assign(5, 6)                       # t=0
        w.run_until(7)
        w.assign(5, 7)                       # t=7
        w.tick()                             # pickup restarts the counter: 7 -> 6
        self.assertEqual(w.car.stopOverCounter, 6)
        self.assertEqual(sorted(e["p"].DF for e in w.car.pendingBoard), [6.0, 7.0])
        w.run_until(10)                      # door-open at counter 5 (t=9) -> both board
        self.assertEqual(w.car.load, 2)
        self.assertEqual(w.car.DF, {6.0, 7.0})
        self.assertEqual(w.car.state, 1)

    def test_state_may_be_nonzero_during_a_drop_off_cycle_without_movement(self):
        """The counter gates movement, not the state (controller.py (a) before (c))."""
        w = _World(start_floor=4.5)
        w.car.state = 1
        rider = Passenger(3.0, 0.0, 5.0)
        rider.carId = 1
        w.P.add(rider)
        w.P.transfer(rider, "travelling")
        rider.board(1, 0.0)
        w.car.P.transfer(rider, "travelling")
        w.car.DF.add(5.0)
        w.car.load = 1
        w.assign(8, 9)                       # up call above keeps state +1 at 5
        w.tick()                             # 4.5 -> 5.0
        w.tick()                             # beginDropoff, counter 7 -> 6
        self.assertEqual(w.car.state, 1)
        for _ in range(6):                   # counter 6 -> 0
            w.tick()
            self.assertEqual(w.car.floor, 5.0)
        self.assertEqual(w.car.stopOverCounter, 0)
        w.tick()
        self.assertEqual(w.car.floor, 5.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
