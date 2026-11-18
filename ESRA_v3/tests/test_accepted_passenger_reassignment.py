"""
tests/test_accepted_passenger_reassignment.py
==============================================
Run from the ESRA_v3/ root:  python tests/test_accepted_passenger_reassignment.py

Regression checks for [A6] (decision/dispatcher.py Dispatcher.assign_call,
car.py Car.beginPickup): a passenger a car has already accepted for
boarding must not be handed to a second car.

The race ([A4] pre-boarding window). beginPickup answers the hall call on
arrival (counter 7) and puts the accepted passengers into the car's
pendingBoard, but they STAY in P.waiting until the doors are open
(counter 5). A new call registered at the same floor and direction inside
that 2 s window is dispatched like any other call, and before [A6] every
dispatcher rewrote carId for ALL waiting passengers at the call floor -
the accepted ones included. The second car then boarded them as well, and
P.served ended up with duplicate rows.

Deterministic reproduction (real engine, real NearestCarDispatcher), the
same geometry as the first duplicate found by analysis/headless_benchmark.py
(periodic traffic, seed 17, two cars at floor 7 going down):

    t=0  p1 (7 -> 1) waits at 7. Cars 1 and 2 are idle at 7.0. The FS tie
         (both d = 0, both counter 0) keeps the first car: car 1 answers
         the call, counter 7, p1 in car 1's pendingBoard, p1 still waiting.
    t=1  p2 (7 -> 2) registers a new down call at 7. FS tie again, broken
         by the SMALLER stop-over counter: car 2 (0) beats car 1 (6).
         Legacy dispatchers wrote carId = 2 to p1 as well -> car 2 opened
         its doors for p1 and p2, car 1 for p1: p1 boarded twice.
    t=2  doors open: p1 boards car 1 (and nothing else), p2 boards car 2.
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
from decision import NearestCarDispatcher

CAR = NS(doorOpeningTime=2, passengerTransferTime=3, doorClosingTime=2,
         carCapacity=10, carCapacityFactor=1, carVelocity=1.5, floorHeight=3)


class _LegacyNearestCar(NearestCarDispatcher):
    """The pre-[A6] write path: every waiting passenger at the call floor
    gets the new car, accepted or not. Used to prove the safety net."""

    @staticmethod
    def assign_call(hall_call, dir_, car_id, P):
        hall_call.carId = car_id
        for passenger in P.waiting[dir_]:
            if passenger.floor == hall_call.floor:
                passenger.carId = car_id
        return 0


class _World:
    """Two cars, real lists, real controller, real dispatcher."""

    def __init__(self, dispatcher_cls=NearestCarDispatcher, nf=8):
        Passenger.reset_id()
        self.building = NS(nf=nf)
        self.cars = [Car(CAR, 1), Car(CAR, 2)]
        for car in self.cars:
            car.floor = car.previousFloor = 7.0
        self.HC, self.P = HallCallLists(), PassengerLists()
        self.dm = dispatcher_cls(NS(stateUpdateTypeForNextDecision="fixed"))
        self.ctrl = Controller(self.dm)
        self.clock = NS(time=0.0, Ts=1.0)
        self.t = 0

    def register(self, floor, DF):
        """A passenger floor -> DF joins the queue now (simulator.generatePassenger)."""
        p = Passenger(float(floor), float(self.t), float(DF))
        self.P.add(p)
        if not any(hc.floor == p.floor for hc in self.HC.waiting[p.direction]):
            self.HC.add(HallCall(float(floor), float(self.t), p.direction))
        return p

    def decide(self):
        self.ctrl.runDecisionProcess(self.building, self.cars, self.HC, self.P)

    def tick(self):
        """experiment.py order: (decision already taken) operate, state update."""
        self.clock.time = float(self.t)
        self.ctrl.operate(self.cars, self.clock, self.HC, self.P)
        self.ctrl.updateCarStatesForNextDecision(self.cars)
        self.t += 1

    def served_ids(self):
        return [p.id for p in self.P.served[1] + self.P.served[2]]

    def run_until_served(self, limit=120):
        while self.t < limit and (any(self.P.waiting[d] or self.P.travelling[d]
                                      for d in (1, 2))):
            self.tick()


def _window(world):
    """t=0: p1 answered by car 1; t=1: p2 registers, dispatched. Returns (p1, p2)."""
    p1 = world.register(7, 1)
    world.decide()                          # t=0: call 7-down -> car 1 (tie, first car)
    world.tick()                            # car 1: beginPickup, counter 7 -> 6
    assert world.cars[0].pendingBoard and world.cars[0].pendingBoard[0]["p"] is p1
    assert p1 in world.P.waiting[2], "accepted passenger stays in P.waiting until doors open"
    assert p1.doorOpeningStartTime == 0.0
    p2 = world.register(7, 2)               # t=1: new same-floor, same-direction call
    world.decide()                          # tie broken by the smaller counter -> car 2
    return p1, p2


class AcceptedPassengerReassignmentTests(unittest.TestCase):

    def test_assign_call_skips_accepted_passengers(self):
        """Unit: the helper leaves accepted passengers with their car."""
        w = _World()
        p1, p2 = _window(w)
        call = w.HC.waiting[2][0]
        self.assertEqual(call.floor, 7.0)
        self.assertEqual(call.carId, 2, "new call goes to the idle car (smaller counter)")
        self.assertEqual(p2.carId, 2)
        self.assertEqual(p1.carId, 1, "accepted passenger keeps the accepting car")
        self.assertEqual(NearestCarDispatcher.assign_call(call, 2, 2, w.P), 1,
                         "exactly one accepted passenger skipped")
        self.assertNotIn(p1, w.cars[1].P.waiting[2], "car 2's service list excludes p1")

    def test_each_passenger_boards_exactly_once(self):
        """Engine: p1 rides car 1, p2 rides car 2, no duplicate served rows."""
        w = _World()
        p1, p2 = _window(w)
        w.tick()                            # t=1: car 2 beginPickup (p2 only)
        self.assertEqual([e["p"] for e in w.cars[1].pendingBoard], [p2])
        self.assertEqual([e["p"] for e in w.cars[0].pendingBoard], [p1])
        w.run_until_served()
        self.assertEqual(sorted(w.served_ids()), sorted({p1.id, p2.id}),
                         "every passenger served exactly once")
        self.assertEqual(p1.carId, 1)
        self.assertEqual(p2.carId, 2)
        self.assertEqual(p1.WT, 0.0)        # accepted at its own arrival tick
        self.assertEqual(p1.WT_board, 2.0)  # doors open two ticks later
        self.assertIsNotNone(p1.DAT)
        self.assertIsNotNone(p2.DAT)

    def test_begin_pickup_rejects_a_passenger_accepted_by_another_car(self):
        """Safety net: a dispatcher that bypasses assign_call cannot make
        a second car board an accepted passenger silently."""
        w = _World(dispatcher_cls=_LegacyNearestCar)
        p1, p2 = _window(w)
        self.assertEqual(p1.carId, 2, "legacy write path reassigned the accepted passenger")
        with self.assertRaisesRegex(RuntimeError, r"already accepted by another car"):
            w.tick()                        # car 2's beginPickup sees p1

    def test_headless_traffic_has_no_duplicate_boarding(self):
        """End to end: the benchmark's periodic traffic, seeds 1-20 (seed 17
        produced dup = 2 on the [A5] engine before [A6]; seed 1 on main)."""
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            "headless_benchmark", os.path.join(root, "analysis", "headless_benchmark.py"))
        hb = importlib.util.module_from_spec(spec)
        argv, sys.argv = sys.argv, [sys.argv[0]]
        try:
            spec.loader.exec_module(hb)
        finally:
            sys.argv = argv
        for seed in range(1, 21):
            with self.subTest(seed=seed):
                m = hb.traffic_run(seed)
                self.assertEqual(m["dup"], 0, f"duplicate served rows for seed {seed}")
                self.assertEqual(m["unserved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
