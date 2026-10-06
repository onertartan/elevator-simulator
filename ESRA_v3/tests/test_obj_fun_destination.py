"""
tests/test_obj_fun_destination.py
==================================
Hand-computed verification of decision/meta/obj_funs/obj_fun_destination
(port of matlab_src/objFuns/objFunDestination.m + NumofCSTrue.m).

Run from the ESRA_v3/ root:  python tests/test_obj_fun_destination.py

Cars are SimpleNamespace stand-ins: the objective only reads velocity,
floor, DF, state, stopOverTime and doorOpeningTime (never mutates them); P is a
SimpleNamespace whose waiting{1,2} lists hold (floor, DF) passengers.
"""
import copy
import os
import sys
from types import SimpleNamespace as NS

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.meta.obj_funs import objFunDestination, numOfCarStopsTrue
from decision.meta.obj_funs.obj_fun_destination import car_waiting_times


def car(floor, state, DF=(), velocity=1.0, velocityFps=1.0,
        stopOverTime=2.0, doorOpeningTime=0.0):
    return NS(floor=float(floor), state=state, DF=set(DF),
              velocity=velocity, velocityFps=velocityFps,
              stopOverTime=stopOverTime, doorOpeningTime=doorOpeningTime)


def test_interfloor_time_uses_velocityFps():
    """[P37] intFloor = 1/velocityFps (= floorHeight/velocity):
    0.5 floors/s -> 2 s per floor."""
    avg = objFunDestination([car(1, 1, velocityFps=0.5)], [2], 1,
                            [[1]], 8, plists(up=[(2, 5)]))
    assert np.allclose(avg, [2.0]), avg   # (2-1) floor * 2 s, 0 stops
    print("PASS  [P37] inter-floor time = floorHeight/velocity")


def plists(up=(), down=()):
    return NS(waiting={1: [NS(floor=f, DF=d) for f, d in up],
                       2: [NS(floor=f, DF=d) for f, d in down]})


def test_idle_car_same_floor_up_passenger_zero_wait():
    """An idle car already at the pickup floor has no travel or prior stops."""
    idle_car = car(3, 0, DF=set(), velocityFps=0.5, stopOverTime=2.0)
    idle_car.capacity = float("inf")
    avg = objFunDestination([idle_car], [3], 1, [[1]], 8,
                            plists(up=[(3, 5)]), "WT")
    # The empty-prefix reversal must not create a negative stop count.
    # A ValueError is a regression failure, not an acceptable result.
    np.testing.assert_array_equal(avg, [0.0])
    print("PASS  idle car at pickup floor: zero passenger waiting time")


def test_up_car_same_floor_down_passenger_zero_wait():
    """Mirror case: an empty up-going car can pick up at its top reversal."""
    up_car = car(3, 1, DF=set(), velocityFps=0.5, stopOverTime=2.0)
    up_car.capacity = float("inf")
    avg = objFunDestination([up_car], [3], 0, [[1]], 8,
                            plists(down=[(3, 1)]), "WT")
    np.testing.assert_array_equal(avg, [0.0])
    print("PASS  up car at down pickup floor: zero passenger waiting time")


def test_idle_car_selects_lower_total_up_route():
    idle = car(4, 0, velocityFps=0.5)
    args = [np.array(values) for values in ([5], [6], [2], [1])]
    wt_up, wt_down = car_waiting_times(idle, *args, 2.0)
    # UP gives [2, 16] (total 18); DOWN gives [18, 4] (total 22).
    # Do not take passenger-wise minima [2, 4], which mix incompatible routes.
    np.testing.assert_array_equal(wt_up, [2.0])
    np.testing.assert_array_equal(wt_down, [16.0])
    np.testing.assert_array_equal(
        objFunDestination([idle], [5, 2], 1, [[1, 1]], 8,
                          plists(up=[(5, 6)], down=[(2, 1)])), [9.0])
    assert idle.state == 0
    print("PASS  idle car selects one complete UP route with lower total wait")


def test_idle_car_selects_down_route_by_passenger_weights():
    idle = car(4, 0, velocityFps=0.5)
    wt_up, wt_down = car_waiting_times(
        idle, np.array([5]), np.array([6]), np.array([2] * 4), np.array([1] * 4), 2.0)
    # Same two calls, four DOWN passengers: UP total 66, DOWN total 34.
    np.testing.assert_array_equal(wt_up, [18.0])
    np.testing.assert_array_equal(wt_down, [4.0] * 4)
    np.testing.assert_allclose(
        objFunDestination([idle], [5, 2], 1, [[1, 1]], 8,
                          plists(up=[(5, 6)], down=[(2, 1)] * 4)), [6.8])
    assert idle.state == 0
    print("PASS  idle car can select DOWN using passenger totals, not call averages")


def test_idle_direction_tie_prefers_up_route():
    # Symmetric routes: UP [2, 14], DOWN [14, 2], both total 16.
    wt_up, wt_down = car_waiting_times(
        car(4, 0, velocityFps=0.5), np.array([5]), np.array([6]),
        np.array([3]), np.array([2]), 2.0)
    np.testing.assert_array_equal(wt_up, [2.0])
    np.testing.assert_array_equal(wt_down, [14.0])
    print("PASS  equal totals retain the UP candidate")


def test_fixed_directions_are_not_reoptimized():
    # A fixed DOWN direction remains DOWN even when UP would cost less.
    wt_up, wt_down = car_waiting_times(
        car(4, -1, velocityFps=0.5), np.array([5]), np.array([6]),
        np.array([2]), np.array([1]), 2.0)
    np.testing.assert_array_equal(wt_up, [18.0])
    np.testing.assert_array_equal(wt_down, [4.0])
    # Likewise a fixed UP direction is preserved with heavier DOWN demand.
    wt_up, wt_down = car_waiting_times(
        car(4, 1, velocityFps=0.5), np.array([5]), np.array([6]),
        np.array([2] * 4), np.array([1] * 4), 2.0)
    np.testing.assert_array_equal(wt_up, [2.0])
    np.testing.assert_array_equal(wt_down, [16.0] * 4)
    print("PASS  signed input directions retain their existing route costs")


def test_idle_empty_and_single_direction_subsets():
    for up_floor, up_df, dn_floor, dn_df, expected_up, expected_down in (
            ([], [], [], [], [], []),
            ([5], [6], [], [], [2.0], []),
            ([], [], [2], [1], [], [4.0])):
        args = [np.array(values, dtype=int)
                for values in (up_floor, up_df, dn_floor, dn_df)]
        before = [values.copy() for values in args]
        wt_up, wt_down = car_waiting_times(car(4, 0, velocityFps=0.5), *args, 2.0)
        np.testing.assert_array_equal(wt_up, expected_up)
        np.testing.assert_array_equal(wt_down, expected_down)
        for actual, original in zip(args, before):
            np.testing.assert_array_equal(actual, original)
    print("PASS  empty/single-direction subsets and read-only passenger arrays")


def test_idle_evaluation_is_pure_and_population_order_independent():
    cars = [car(4, 0, velocityFps=0.5), car(8, 0, velocityFps=0.5)]
    passengers = plists(up=[(5, 6)], down=[(2, 1)] * 4)
    before_cars, before_passengers = copy.deepcopy((cars, passengers))
    rows = np.array([[1, 1], [1, 2], [2, 1], [2, 2], [1, 1]])

    def evaluate(population):
        return objFunDestination(cars, [5, 2], 1, population, 8, passengers)

    batch = evaluate(rows)
    np.testing.assert_array_equal(evaluate(rows[::-1]), batch[::-1])
    np.testing.assert_array_equal(
        np.concatenate([evaluate(row.reshape(1, -1)) for row in rows]), batch)
    np.testing.assert_array_equal(evaluate(rows), batch)
    assert cars == before_cars and passengers == before_passengers
    print("PASS  idle route selection leaves inputs intact across populations and calls")


def test_numOfCarStopsTrue():
    # stops over unique({2,5} + {4,6} + {3}) = [2,3,4,5,6]
    atF, atDF, seg = numOfCarStopsTrue([2, 5], [4, 6], [3], False, 0)
    assert list(atF) == [1, 4] and list(atDF) == [3, 5] and seg == 5, \
        "ascending ranks over floors + passenger DFs + car DFs"
    atF, atDF, seg = numOfCarStopsTrue([2, 5], [4, 6], [3], True, 0)
    assert list(atF) == [5, 2] and list(atDF) == [3, 1] and seg == 5, \
        "reversed ranks"
    atF, atDF, _ = numOfCarStopsTrue([2, 5], [4, 6], [3], False, 2)
    assert list(atF) == [3, 6] and list(atDF) == [5, 7], \
        "previous-stops offset applies to both outputs"
    print("PASS  numOfCarStopsTrue ranks, reverse, offset [P33]")


def test_up_passengers_destination_stops():
    """Up car: the first passenger's DESTINATION becomes an extra stop
    that delays the second passenger - the information Conventional1
    does not have."""
    # floor 1, passengers (2->5) and (6->7); stop floors {2,5,6,7}
    # p(2->5): (2-1)*1 + (1-1)*2 = 1
    # p(6->7): (6-1)*1 + (3-1)*2 = 9   (stops at 2 AND at 5 first)
    # (objFunConventional1 on the same calls: [1, 7] -> mean 4)
    avg = objFunDestination([car(1, 1)], [2, 6], 2, [[1, 1]], 8,
                            plists(up=[(2, 5), (6, 7)]))
    assert np.allclose(avg, [5.0]), avg
    print("PASS  up car: passenger DFs enter the stop sequence")


def test_up_car_down_reversal():
    """Up car with DF between segments, down passenger served after the
    top reversal."""
    # car floor 2, DF={5}, up pass (3->4), down pass (6->1)
    # seg1: stops {3}u{4}u{5}: (3-2)*1 + 0 = 1;  prev=3
    # seg2: MAKS=max(5,6)=6, stops [6,1]: rank 1+3=4
    #       (6-2 + 6-6)*1 + (4-1)*2 = 10
    avg = objFunDestination([car(2, 1, DF={5})], [3, 6], 1, [[1, 1]], 6,
                            plists(up=[(3, 4)], down=[(6, 1)]))
    assert np.allclose(avg, [5.5]), avg
    print("PASS  up car, down passenger after top reversal")


def test_reversal_DF_correction():
    """Same route but the down call floor IS the committed DF: the
    shared reversal stop is not double-counted (prev -= 1)."""
    # car floor 2, DF={6}: MAKS=max(4,2,6)=6 == max(P_dw_all_floor)
    # seg1: stops {3}u{4}u{6}: 1;  prev=3 -> corrected to 2
    # seg2: stops [6,1]: rank 1+2=3;  (6-2+6-6)*1 + (3-1)*2 = 8
    avg = objFunDestination([car(2, 1, DF={6})], [3, 6], 1, [[1, 1]], 6,
                            plists(up=[(3, 4)], down=[(6, 1)]))
    assert np.allclose(avg, [4.5]), avg
    print("PASS  shared reversal/DF stop not double-counted")


def test_down_car_reversal_DF_correction():
    """Mirror of the existing shared-stop test: preserve the bottom correction."""
    # car floor 5, DF={1}, down (4->3), up (1->6).
    # First segment: stops [4,3,1], WT=1, prev=3.
    # Shared floor 1: prev=2, up pickup rank=1+2=3, WT=4+(3-1)*2=8.
    avg = objFunDestination([car(5, -1, DF={1})], [1, 4], 1,
                            [[1, 1]], 6, plists(up=[(1, 6)], down=[(4, 3)]))
    np.testing.assert_array_equal(avg, [4.5])
    print("PASS  down car: shared reversal/DF stop not double-counted")


def test_down_car_full_route():
    """Down car: down-below, then all-up, then down-above segments,
    with MAKS coming from an up passenger's destination."""
    # car floor 4, state -1, no DF; up (2->5), down (3->1) and (6->5)
    # HC = [2 | 3, 6], ups=1, all to car 1
    # MAKS=max(P_up_all_DF)=5, MINI=min(1, 4)=1
    # seg1 dw_1 (3->1): stops [3,1]: (4-3)*1 + 0 = 1;      prev=2
    # seg2 up (2->5):   stops [2,5]: rank 1+2=3, MINI=1
    #                   ((4-1)+(2-1))*1 + (3-1)*2 = 8;     prev=2
    # seg3 dw_2 (6->5): MAKS=max(5,6)=6, stops [6,5]: rank 1+2=3
    #                   ((4-1)+(6-1)+(6-6))*1 + (3-1)*2 = 12
    avg = objFunDestination([car(4, -1)], [2, 3, 6], 1, [[1, 1, 1]], 6,
                            plists(up=[(2, 5)], down=[(3, 1), (6, 5)]))
    assert np.allclose(avg, [(8 + 1 + 12) / 3]), avg
    print("PASS  down car three-segment route")


def test_two_passengers_one_call():
    """Two passengers behind ONE hall call: ismember matches both, and
    both destinations enter the stop sequence."""
    # car floor 1 up; passengers (3->4) and (3->6); stops {3,4,6}
    # both: (3-1)*1 + (1-1)*2 = 2
    avg = objFunDestination([car(1, 1)], [3], 1, [[1]], 6,
                            plists(up=[(3, 4), (3, 6)]))
    assert np.allclose(avg, [2.0]), avg
    print("PASS  multiple passengers per hall call")


def test_multi_row_two_cars():
    """Two chromosome rows, two cars; a car with no assigned calls
    contributes nothing (all masks empty)."""
    cars = [car(1, 1), car(5, -1)]
    P = plists(up=[(2, 4), (3, 4)])
    # row 1 [1,1]: car1 takes both; stops {2,3}u{4}
    #   p(2->4): 1;  p(3->4): (3-1) + 1*2 = 4  -> mean 2.5
    # row 2 [1,2]: car1 takes (2->4): stops {2,4} -> 1
    #   car2 (floor 5, down) takes (3->4) as up-after-reversal:
    #   MINI=min(3,5)=3, stops {3}u{4}: ((5-3)+(3-3))*1 + 0 = 2
    #   -> mean 1.5
    avg = objFunDestination(cars, [2, 3], 2, [[1, 1], [1, 2]], 6, P)
    assert np.allclose(avg, [2.5, 1.5]), avg
    print("PASS  multi-row population, idle second car no-op")


def test_jt_ctt_not_ported():
    """[P35] MATLAB 'JT' silently returns zeros (local TOTAL) and 'CTT'
    errors on undefined WT1/WT2 - the port refuses both loudly."""
    for param in ("JT", "CTT"):
        try:
            objFunDestination([car(1, 1)], [2], 1, [[1]], 5,
                              plists(up=[(2, 3)]), param)
            raise AssertionError(f"{param} should raise NotImplementedError")
        except NotImplementedError:
            pass
    print("PASS  [P35] JT/CTT raise NotImplementedError")


def test_pickup_door_opening_same_floor():
    for state, ups, passengers in (
            (0, 1, plists(up=[(3, 5)])),
            (1, 0, plists(down=[(3, 1)])),
            (-1, 1, plists(up=[(3, 5)])),
            (0, 0, plists(down=[(3, 1)]))):
        avg = objFunDestination(
            [car(3, state, velocityFps=0.5, stopOverTime=7, doorOpeningTime=2)],
            [3], ups, [[1]], 8, passengers, "WT")
        np.testing.assert_array_equal(avg, [0.0])
    print("PASS  same-floor pickup: zero wait to opening start, including nonzero doors")


def test_pickup_opening_does_not_repeat_prior_stop_over():
    # Stops {3,4,6,7}: WT(3)=4; WT(6)=10+2*7=24.
    avg = objFunDestination(
        [car(1, 1, velocityFps=0.5, stopOverTime=7, doorOpeningTime=2)],
        [3, 6], 2, [[1, 1]], 8, plists(up=[(3, 4), (6, 7)]), "WT")
    np.testing.assert_array_equal(avg, [14.0])
    print("PASS  prior full stops retained, no pickup opening added")


def test_car_specific_opening_all_segments_and_passenger_weights():
    rows = np.array([[1] * 6, [2] * 6, [1, 2, 2, 1, 1, 2]])
    calls = [2, 4, 6, 2, 4, 6]
    P = plists(up=[(2, 7), (4, 8), (4, 6), (6, 8)],
               down=[(2, 1), (4, 1), (6, 1), (6, 3)])
    cars = [car(4, 1, DF={2, 6}, stopOverTime=7),
            car(4, -1, DF={2, 6}, stopOverTime=7)]
    baseline = objFunDestination(cars, calls, 3, rows, 8, P, "WT")
    doors = np.array([1.0, 3.0])
    for c, opening in zip(cars, doors):
        c.doorOpeningTime = opening
    actual = objFunDestination(cars, calls, 3, rows, 8, P, "WT")
    np.testing.assert_allclose(actual, baseline)
    assert [c.state for c in cars] == [1, -1]
    print("PASS  car-specific pickup opening excluded across all route segments")


def test_invalid_door_opening_is_rejected():
    for opening in (-1, float("nan"), float("inf")):
        try:
            objFunDestination([car(3, 0, doorOpeningTime=opening)], [3], 1,
                              [[1]], 8, plists(up=[(3, 5)]), "WT")
        except ValueError as exc:
            assert "doorOpeningTime" in str(exc)
        else:
            raise AssertionError("Invalid door-opening time was accepted")
    print("PASS  invalid pickup door-opening time rejected")


def test_positive_opening_cannot_hide_negative_route_cost():
    from unittest.mock import patch
    with patch("decision.meta.obj_funs.obj_fun_destination.numOfCarStopsTrue",
               return_value=(np.array([0]), np.array([1]), 2)):
        try:
            objFunDestination([car(3, 1, doorOpeningTime=5)], [3], 1,
                              [[1]], 8, plists(up=[(3, 5)]), "WT")
        except ValueError as exc:
            assert "negative waiting times" in str(exc)
        else:
            raise AssertionError("Positive pickup opening hid a negative route cost")
    print("PASS  pickup opening cannot mask negative route waiting time")


if __name__ == "__main__":
    test_numOfCarStopsTrue()
    test_up_passengers_destination_stops()
    test_up_car_down_reversal()
    test_reversal_DF_correction()
    test_down_car_full_route()
    test_two_passengers_one_call()
    test_multi_row_two_cars()
    test_jt_ctt_not_ported()
    test_interfloor_time_uses_velocityFps()
    test_idle_car_same_floor_up_passenger_zero_wait()
    test_up_car_same_floor_down_passenger_zero_wait()
    test_down_car_reversal_DF_correction()
    test_pickup_door_opening_same_floor()
    test_pickup_opening_does_not_repeat_prior_stop_over()
    test_car_specific_opening_all_segments_and_passenger_weights()
    test_invalid_door_opening_is_rejected()
    test_positive_opening_cannot_hide_negative_route_cost()
    test_idle_car_selects_lower_total_up_route()
    test_idle_car_selects_down_route_by_passenger_weights()
    test_idle_direction_tie_prefers_up_route()
    test_fixed_directions_are_not_reoptimized()
    test_idle_empty_and_single_direction_subsets()
    test_idle_evaluation_is_pure_and_population_order_independent()
    print("\nALL objFunDestination TESTS PASSED")
