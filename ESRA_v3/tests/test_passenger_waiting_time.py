"""Real-engine regression checks; python tests/test_passenger_waiting_time.py."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from car import Car
from controller import Controller
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists
from simulator import Simulator


def car(opening=2, capacity=10, car_id=1):
    c = Car(NS(doorOpeningTime=opening, passengerTransferTime=3,
               doorClosingTime=2, carCapacity=capacity, carCapacityFactor=1,
               carVelocity=1.5, floorHeight=3), car_id)
    c.floor = c.previousFloor = 3
    c.state = 1
    return c


def assign(c, HC, P, p):
    p.carId = c.id
    calls = [h for h in HC.waiting[p.direction] if h.floor == p.floor]
    if not calls:
        h = HallCall(p.floor, p.QJT, p.direction)
        HC.add(h)
        calls = [h]
    for h in calls:
        h.carId = c.id
    c.updateServiceList(HC, P)


def waiter(c, HC, P, qjt=0, df=5):
    p = Passenger(3, qjt, df)
    P.add(p)
    assign(c, HC, P, p)
    return p


def step(cars, HC, P, clock):
    Controller(None).operate(cars, clock, HC, P)


def finish_boarding(c, HC, P, clock):
    for _ in range(40):
        if not c.pendingBoard:
            return
        step([c], HC, P, clock)
    raise AssertionError("boarding did not finish within the small test budget")


class PassengerWaitingTimeTests(unittest.TestCase):
    def test_primary_freezes_but_animation_and_boarding_stay_at_full_open(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        p = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        self.assertEqual((p.WT, p.WT_board, p.doorOpeningStartTime), (5, 6, 5))
        self.assertIsNone(p.BT)
        self.assertIn(p, P.waiting[1])
        self.assertEqual(c.load, 0)
        self.assertEqual(c.pendingBoard[0]["p"], p)
        step([c], HC, P, clock)
        self.assertEqual((p.WT, p.WT_board), (5, 7))
        self.assertIsNone(p.BT)
        step([c], HC, P, clock)
        self.assertEqual((p.WT, p.WT_board, p.BT), (5, 7, 7))
        self.assertNotIn(p, P.waiting[1])
        self.assertIn(p, P.travelling[1])
        self.assertEqual(c.boarding, [{"id": p.id, "dir": 1}])
        self.assertEqual(c.load, 1)
        p.alight(15)
        self.assertEqual((p.TrT, p.TTD), (8, 15))
        self.assertEqual(p.WT_board + p.TrT, p.TTD)

    def test_same_floor_including_zero_and_fractional_opening(self):
        for opening, ts, bt in ((0, 1, 0), (2, 1, 2), (1.5, 1, 2), (0.5, 0.25, 0.5)):
            with self.subTest(opening=opening, ts=ts):
                c, HC, P = car(opening), HallCallLists(), PassengerLists()
                p = waiter(c, HC, P)
                clock = NS(time=0, Ts=ts)
                step([c], HC, P, clock)
                finish_boarding(c, HC, P, clock)
                self.assertEqual((p.WT, p.BT, p.WT_board), (0, bt, bt))
                if opening == 1.5:
                    self.assertNotEqual(p.WT, p.WT_board - opening)

    def test_down_direction_same_definition(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        c.state = -1
        p = waiter(c, HC, P, qjt=1, df=1)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((p.WT, p.WT_board, p.BT), (4, 6, 7))

    def test_full_car_does_not_end_wait_later_accepting_car_does(self):
        # Construct both cars before passengers (PassengerLists resets IDs).
        full, accepting = car(capacity=1), car(opening=4, car_id=2)
        HC, P = HallCallLists(), PassengerLists()
        full.load = 1
        p = waiter(full, HC, P)
        clock = NS(time=3, Ts=1)
        step([full], HC, P, clock)
        self.assertIsNone(p.doorOpeningStartTime)
        self.assertIsNone(p.BT)
        self.assertEqual(p.WT, 4)
        self.assertFalse(full.pendingBoard)
        assign(accepting, HC, P, p)
        clock.time = 6
        step([accepting], HC, P, clock)
        finish_boarding(accepting, HC, P, clock)
        self.assertEqual((p.carId, p.doorOpeningStartTime, p.WT, p.BT, p.WT_board),
                         (2, 6, 6, 10, 10))

    def test_capacity_reserved_only_for_accepted_passengers(self):
        c, HC, P = car(capacity=1), HallCallLists(), PassengerLists()
        accepted = waiter(c, HC, P)
        refused = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual(accepted.WT, 5)
        self.assertIsNone(refused.doorOpeningStartTime)
        self.assertIsNone(refused.BT)
        self.assertEqual(refused.WT, clock.time)
        self.assertEqual(c.load, 1)

    def test_combined_dropoff_frees_capacity_at_unchanged_event(self):
        c, HC, P = car(capacity=1), HallCallLists(), PassengerLists()
        alighter = Passenger(1, -1, 3)
        alighter.board(c.id, -1)
        P.travelling[1].append(alighter)
        c.P.travelling[1].append(alighter)
        c.load = 1
        c.DF.add(3)
        p = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        self.assertIsNone(alighter.DAT)
        self.assertIsNone(p.BT)
        self.assertEqual(p.WT, 5)
        self.assertEqual(c.load, 1)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((alighter.DAT, p.BT, c.load), (7, 7, 1))
        self.assertIn(alighter, P.served[1])
        self.assertIn(p, P.travelling[1])

    def test_arrival_during_opening_and_counter_restart(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        first = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        newcomer = waiter(c, HC, P, qjt=6)
        step([c], HC, P, clock)  # legacy timer restarts, original opening stays
        self.assertEqual(c.doorOpeningStartTime, 5)
        self.assertEqual(c.stopOverCounter, 6)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((first.WT, first.WT_board, first.BT), (5, 8, 8))
        self.assertEqual((newcomer.WT, newcomer.WT_board, newcomer.BT), (0, 2, 8))

    def test_arrival_during_open_transfer_has_zero_primary_wait(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        first = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)  # time=8, doors open, first BT=7
        newcomer = waiter(c, HC, P, qjt=8)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((first.WT, first.BT), (5, 7))
        self.assertEqual((newcomer.doorOpeningStartTime, newcomer.WT, newcomer.BT),
                         (5, 0, 10))

    def test_arrival_during_closing_starts_new_opening_event(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        first = waiter(c, HC, P)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        while clock.time < 10:  # counter == closing time
            step([c], HC, P, clock)
        newcomer = waiter(c, HC, P, qjt=9)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual(first.doorOpeningStartTime, 5)
        self.assertEqual((newcomer.doorOpeningStartTime, newcomer.WT, newcomer.BT),
                         (10, 1, 12))

    def test_dropoff_opening_can_accept_a_later_arrival(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        c.DF.add(3)
        clock = NS(time=5, Ts=1)
        step([c], HC, P, clock)
        p = waiter(c, HC, P, qjt=6)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((p.doorOpeningStartTime, p.WT, p.BT), (5, 0, 8))

    def test_expired_cycle_and_reset_do_not_reuse_old_timestamp(self):
        c, HC, P = car(), HallCallLists(), PassengerLists()
        c.beginDropoff(5)
        c.stopOverCounter = 0
        p = waiter(c, HC, P, qjt=10)
        clock = NS(time=20, Ts=1)
        step([c], HC, P, clock)
        finish_boarding(c, HC, P, clock)
        self.assertEqual((p.doorOpeningStartTime, p.WT, p.BT), (20, 10, 22))
        c.reset()
        self.assertIsNone(c.doorOpeningStartTime)
        self.assertIsNone(c._doorCycleFloor)

    def test_replay_resets_outcomes_without_mutating_record_even_for_legacy(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                c, HC, P = car(), HallCallLists(), PassengerLists()
                original = Passenger(3, 0, 5)
                original.start_pickup(4)
                original.board(9, 6)
                original.alight(9)
                if legacy:
                    del original.doorOpeningStartTime
                    del original.WT_board
                P.served[1].append(original)
                sim = object.__new__(Simulator)
                sim.time, sim.dataType = 0, 2
                sim.checkNewPassenger(HC, P, None)
                replayed = P.waiting[1][0]
                self.assertIsNot(replayed, original)
                self.assertEqual(replayed.id, original.id)
                self.assertEqual((replayed.WT, replayed.WT_board, replayed.carId), (0, 0, 0))
                self.assertIsNone(replayed.doorOpeningStartTime)
                self.assertIsNone(replayed.BT)
                self.assertIsNone(replayed.DAT)
                assign(c, HC, P, replayed)
                clock = NS(time=10, Ts=1)
                step([c], HC, P, clock)
                finish_boarding(c, HC, P, clock)
                self.assertEqual((replayed.WT, replayed.WT_board, replayed.BT), (10, 12, 12))
                self.assertEqual((original.WT, original.BT, original.DAT), (4, 6, 9))

    def test_initial_cabin_passenger_sentinel_preserved(self):
        p = Passenger(3, -1, 5)
        p.board(1, -1)
        self.assertEqual((p.QJT, p.BT, p.WT, p.WT_board), (-1, -1, 0, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
