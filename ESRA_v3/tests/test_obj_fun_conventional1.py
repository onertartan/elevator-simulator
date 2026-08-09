"""
tests/test_obj_fun_conventional1.py
====================================
Hand-computed verification of decision/meta/obj_funs/obj_fun_conventional1
(port of matlab_src/objFuns/objFunConventional1.m + ESRA_v2 NumofCS.m).

Run from the ESRA_v3/ root:  python tests/test_obj_fun_conventional1.py

Cars are SimpleNamespace stand-ins: the objective only reads/writes
velocity, floor, DF, state and stopOverTime, and the real dispatcher
passes deep copies anyway [P14].
"""
import os
import sys
from types import SimpleNamespace as NS

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.meta.obj_funs import objFunConventional1, numOfCarStops


def car(floor, state, DF=(), velocity=1.0, velocityFps=1.0,
        stopOverTime=2.0):
    return NS(floor=float(floor), state=state, DF=set(DF),
              velocity=velocity, velocityFps=velocityFps,
              stopOverTime=stopOverTime)


def test_interfloor_time_uses_velocityFps():
    """[P37] intFloor = 1/velocityFps (= floorHeight/velocity):
    0.5 floors/s -> 2 s per floor."""
    avg = objFunConventional1([car(1, 1, velocityFps=0.5)], [3], 1,
                              [[1]], nf=5)
    assert np.allclose(avg, [4.0]), avg   # (3-1) floors * 2 s, 0 stops
    print("PASS  [P37] inter-floor time = floorHeight/velocity")


def test_numOfCarStops():
    stops, prev = numOfCarStops([2, 5, 7], [3], reverse=False,
                                numStopsPrevious=0)
    assert list(stops) == [1, 3, 4] and prev == 4, \
        "ascending ranks over unique(HC + DF)"
    stops, prev = numOfCarStops([2, 5, 7], [3], reverse=True,
                                numStopsPrevious=0)
    assert list(stops) == [4, 2, 1] and prev == 4, "reversed ranks"
    stops, prev = numOfCarStops([4], [], reverse=False, numStopsPrevious=2)
    assert list(stops) == [3] and prev == 1, "previous-stops offset"
    print("PASS  numOfCarStops ranks, reverse, offset [P18]")


def test_up_calls_above():
    """Car going up, two up calls above: WT = travel + stops so far."""
    # floor 1 -> call 3: 2 floors, 0 stops before  -> 2
    # floor 1 -> call 4: 3 floors, 1 stop (at 3)   -> 3 + 2 = 5
    avg = objFunConventional1([car(1, 1)], [3, 4], 2, [[1, 1]], nf=5)
    assert np.allclose(avg, [3.5]), avg
    print("PASS  up car, up calls above: travel + stopOver stops")


def test_mixed_up_and_down():
    """Car going up with a committed DF between the segments."""
    # car floor 2, DF={5}, up call 3, down call 6, nf=6
    # up seg:   (3-2) + 0*2 = 1        (stop ranks over {3,5})
    # down seg: (6-2 + 6-6) + 2*2 = 8  (2 stops before: 3 and 5)
    avg = objFunConventional1([car(2, 1, DF={5})], [3, 6], 1, [[1, 1]], nf=6)
    assert np.allclose(avg, [4.5]), avg
    print("PASS  up car, DF between up and down segments")


def test_reversal_DF_correction():
    """Down call at the top reversal floor that is also a DF: the shared
    stop is not double-counted (objFunConventional1.m lines 71-73)."""
    # car floor 2, DF={5}, single down call at 5, nf=5:
    # MAKS=max(DF,floor)=5, prev=len(DF)=1, correction -> prev=0
    # WT = (5-2 + 5-5) + (1-1)*2 = 3
    avg = objFunConventional1([car(2, 1, DF={5})], [5], 0, [[1]], nf=5)
    assert np.allclose(avg, [3.0]), avg
    print("PASS  shared reversal/DF stop not double-counted")


def test_idle_state_leak_across_rows():
    """!!! MATLAB handle quirk: the idle-direction decision made while
    scoring row 1 persists into row 2 of the SAME call."""
    cars = [car(3, 0, DF={1}), car(1, 1)]
    HC, ups = [4, 2], 1
    chrom = [[2, 1],   # row 1: car1 takes down@2 -> decides state=-1
             [1, 2]]   # row 2: car1 takes up@4 with LEAKED state=-1
    # row 1: car2 up@4 from floor 1 -> 3; car1 down@2 from 3 -> 1; mean 2
    # row 2: car1 (state -1, MIN=min(DF+floor)=1):
    #        ((3-1)+(4-1)) + (3-1)*2 = 9;  car2 down@2 -> 1;  mean 5
    avg = objFunConventional1(cars, HC, ups, chrom, nf=5)
    assert np.allclose(avg, [2.0, 5.0]), avg

    # fresh copies (as the [P14] wrapper provides per call) -> row 2
    # scored alone gives the un-leaked cost
    cars = [car(3, 0, DF={1}), car(1, 1)]
    avg = objFunConventional1(cars, HC, ups, [[1, 2]], nf=5)
    assert np.allclose(avg, [2.0]), avg   # car1 idle->up: (4-3)+1*2=3; mean 2
    print("PASS  !!! idle-state decision leaks across chromosome rows")


def test_down_car_full_route():
    """Down car: down-below, then all-up, then down-above segments."""
    # car floor 4, state -1, no DF, nf=6; calls: up@2, down@3, down@6
    # HC order: [2 | 3, 6], ups=1, all assigned to car 1
    # seg1 dw_1=[3]: (4-3) + 0*2 = 1;  prev=1
    # seg2 up=[2]: stops {2}, rank 1+1=2; MIN=min(2,1)=1
    #      ((4-1)+(2-1)) + (2-1)*2 = 6; prev=1
    # seg3 dw_2=[6]: MAKS=6 (HC_up nonempty branch), stops rank 1+1=2
    #      ((4-1)+(6-1)+(6-6)) + (2-1)*2 = 10
    avg = objFunConventional1([car(4, -1)], [2, 3, 6], 1, [[1, 1, 1]], nf=6)
    assert np.allclose(avg, [(6 + 1 + 10) / 3]), avg
    print("PASS  down car three-segment route")


if __name__ == "__main__":
    test_numOfCarStops()
    test_up_calls_above()
    test_mixed_up_and_down()
    test_reversal_DF_correction()
    test_idle_state_leak_across_rows()
    test_down_car_full_route()
    test_interfloor_time_uses_velocityFps()
    print("\nALL objFunConventional1 TESTS PASSED")
