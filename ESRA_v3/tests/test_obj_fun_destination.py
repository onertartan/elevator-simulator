"""
tests/test_obj_fun_destination.py
==================================
Hand-computed verification of decision/meta/obj_funs/obj_fun_destination
(port of matlab_src/objFuns/objFunDestination.m + NumofCSTrue.m).

Run from the ESRA_v3/ root:  python tests/test_obj_fun_destination.py

Cars are SimpleNamespace stand-ins: the objective only reads velocity,
floor, DF, state and stopOverTime (never mutates them); P is a
SimpleNamespace whose waiting{1,2} lists hold (floor, DF) passengers.
"""
import os
import sys
from types import SimpleNamespace as NS

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.meta.obj_funs import objFunDestination, numOfCarStopsTrue


def car(floor, state, DF=(), velocity=1.0, velocityFps=1.0,
        stopOverTime=2.0):
    return NS(floor=float(floor), state=state, DF=set(DF),
              velocity=velocity, velocityFps=velocityFps,
              stopOverTime=stopOverTime)


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
    print("\nALL objFunDestination TESTS PASSED")
