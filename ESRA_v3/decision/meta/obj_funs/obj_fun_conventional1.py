"""
decision/meta/obj_funs/obj_fun_conventional1.py
================================================
Port of matlab_src/objFuns/objFunConventional1.m - the conventional
estimated-waiting-time objective for the metaheuristic dispatchers.

For every chromosome row (one car label per hall call, up calls first
then down calls - the [P17] floor-sorted encoding built by
MetaheuristicDispatcher.dispatch), it walks each car's collective
service route in three direction segments and estimates the waiting
time of every hall call as

    travel_time_to_call + (stops_before_call) * stopOverTime

returning the population's per-row mean waiting time (lower = better).
Plugs into startData.objFun with the [P13] wrapper signature:
objFun(cars_copy, HC_all, HC_numofups, population, nf, P, "WT").
The wrapper passes fresh DEEP COPIES of the cars on every call [P14],
so the in-place car.state writes below never touch the live fleet.

Deviation notes (continuing the [P#] family):

  [P18] numOfCarStops ports matlab_src/objFuns/NumofCS.m (identical to
       the ESRA_v2 original). The MATLAB per-element
       `find(HC(i)==CAR_STOP_floors)` linear scan is replaced by one
       dict {floor: rank} built per segment - O(1) lookups, same ranks.
       `unique([HC CAR_DF])` becomes a sorted set-union.
  [P19] car.DF is a set in the port (car.py); sorted(car.DF) reproduces
       MATLAB's ascending numeric vector. The corrections that MATLAB
       checks against cars(i).DF use the ORIGINAL floors, while the
       copy consumed by numOfCarStops (MATLAB's `Z=[]`) is a separate
       local.
  [P20] WT segments are written with vectorized numpy slices
       (WT[idx] = ...) instead of MATLAB's logical-index scatter -
       identical values, one pass per segment.
  [P21] MATLAB `if (HC_up)` (objFunConventional1.m line 117) is array
       truthiness: true iff HC_up is nonempty AND all-nonzero. Floors
       are >= 1, so the port uses a plain nonempty test.
  [P22] MATLAB min([])/max([]) return empty and would only propagate
       into branches that are themselves skipped when the source list
       is empty; the port guards those assignments (MIN/MAKS keep
       their previous value, which is then never read).

  [P37] intFloor = 1/velocityFps = floorHeight/velocity - the
       dimensionally-correct inter-floor travel time (2 s at the GUI
       defaults: 3 m floors / 1.5 m/s), so estimated travel and
       stop-over costs share real seconds. Deviation by decision
       (2026-08): ESRA_v2 used 1/velocity (m/s); the corrected
       objFunConventional1.m already reads velocityFps, and BOTH
       Python objectives now follow it.

MATLAB quirks preserved (flagged !!!):
  * !!! The idle-car direction decision WRITES car.state, and MATLAB
    cars are handle objects - so the decision made while scoring
    chromosome row n LEAKS into rows n+1.. of the same call. The port
    mutates the per-call deep copies the same way.
  * The containers.Map memoization is commented out in the .m source
    and stays out here - it would also be unsound under the state-leak
    quirk above (identical rows can score differently).
"""
from __future__ import annotations

from typing import Any, List, Sequence, Tuple

import numpy as np


def numOfCarStops(hcFloors: Sequence[int], carDF: Sequence[int],
                  reverse: bool, numStopsPrevious: int
                  ) -> Tuple[np.ndarray, int]:
    """
    [P18] Port of NumofCS.m: rank every hall-call floor within this
    direction segment's stop sequence (hall calls + committed car
    destination floors), offset by the stops already accumulated in
    earlier segments. Floors are integer floor numbers (1..nf).

    Returns (stops_at_each_hc, stops_in_this_segment).
    """
    stopFloors = sorted(set(hcFloors) | set(carDF))
    if reverse:                       # car serves this segment downwards
        stopFloors.reverse()
    rank = {floor: k for k, floor in enumerate(stopFloors, start=1)}
    stopsAtHC = np.array([rank[floor] + numStopsPrevious
                          for floor in hcFloors])
    return stopsAtHC, len(stopFloors)


def objFunConventional1(cars: List[Any], HC: Sequence[int],
                        HC_numofups: int, chrom: Any, nf: int,
                        P: Any = None, costType: Any = None) -> np.ndarray:
    """
    objFunConventional1(cars, HC, HC_numofups, chrom, nf, ~, ~)

    cars:         per-call deep copies of the fleet ([P14]; mutated - see
                  the !!! state-leak quirk in the module docstring)
    HC:           all waiting hall-call floors, up calls then down calls
    HC_numofups:  how many leading entries of HC are up calls
    chrom:        (nPop, len(HC)) car labels 1..len(cars)
    nf:           number of floors
    P, costType:  ignored (MATLAB `~, ~`)

    Returns the per-row mean estimated waiting time of hall calls (mean system response time), shape (nPop,).
    """
    chrom = np.asarray(chrom)
    HC_arr = np.asarray(HC, dtype=int)   # floor numbers, 1..nf
    numHC = len(HC_arr)
    intFloor = 1.0 / cars[0].velocityFps    # [P37] floorHeight/velocity
    average = np.zeros(chrom.shape[0])

    for n in range(chrom.shape[0]):
        WT = np.zeros(numHC)

        for label, car in enumerate(cars, start=1):
            floor = car.floor
            DF = sorted(car.DF)                # [P19]
            stopOver = car.stopOverTime

            # Calls this chromosome row assigns to this car, split into
            # the three route segments (indices index into WT).
            up_idx = np.flatnonzero(chrom[n, :HC_numofups] == label)
            HC_up = HC_arr[up_idx]
            m = HC_up >= floor
            up1_idx, HC_up_1 = up_idx[m], HC_up[m]      # up calls at/above
            up2_idx, HC_up_2 = up_idx[~m], HC_up[~m]    # up calls below

            dw_idx = HC_numofups + np.flatnonzero(chrom[n, HC_numofups:] == label)
            HC_dw = HC_arr[dw_idx]
            m = HC_dw <= floor
            dw1_idx, HC_dw_1 = dw_idx[m], HC_dw[m]      # down calls at/below
            dw2_idx, HC_dw_2 = dw_idx[~m], HC_dw[~m]    # down calls above

            Z: List[int] = list(DF)     # consumed by the first segment
            MIN = 1.0
            MAKS = nf
            prev = 0                    # stops accumulated so far

            # ---- idle car: pick a direction (!!! leaks across rows) --
            if car.state == 0:
                above = np.concatenate([HC_up_1, HC_dw_2])
                below = np.concatenate([HC_up_2, HC_dw_1])
                if above.size and not below.size:
                    car.state = 1
                elif not above.size and below.size:
                    car.state = -1
                elif above.size and below.size:
                    u = min(above.min(), 2 * nf)
                    d = max(below.max(), -nf)
                    car.state = -1 if abs(u - floor) > abs(d - floor) else 1

            # ================= CAR MOVING UP ==========================
            if car.state == 1:
                # 1) up calls at/above the car
                if HC_up_1.size:
                    stopsAt, prev = numOfCarStops(HC_up_1, Z, False, prev)
                    WT[up1_idx] = ((HC_up_1 - floor) * intFloor
                                   + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    MAKS = max([*DF, floor])                        # [P22]
                    prev = len(DF)

                # 2) all down calls (served after the top reversal)
                if HC_dw.size:
                    if DF and not HC_up_1.size and HC_dw.max() == MAKS:
                        prev -= 1      # reversal floor is already a DF stop
                    MAKS = max(MAKS, HC_dw.max())
                    stopsAt, prev = numOfCarStops(HC_dw, Z, True, prev)
                    WT[dw_idx] = ((MAKS - floor + MAKS - HC_dw) * intFloor
                                  + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    if HC_up_2.size:                                # [P22]
                        MIN = HC_up_2.min()

                # 3) up calls below the car (served after the bottom
                #    reversal)
                if HC_up_2.size:
                    if DF and not HC_dw.size and HC_up_2.min() == MIN:
                        prev -= 1
                    stopsAt, prev = numOfCarStops(HC_up_2, Z, False, prev)
                    WT[up2_idx] = (((MAKS - floor) + (MAKS - MIN)
                                    + (HC_up_2 - MIN)) * intFloor
                                   + (stopsAt - 1) * stopOver)

            # ============ CAR MOVING DOWN (or still idle) =============
            if car.state != 1:
                # 1) down calls at/below the car
                if HC_dw_1.size:
                    stopsAt, prev = numOfCarStops(HC_dw_1, Z, True, prev)
                    WT[dw1_idx] = ((floor - HC_dw_1) * intFloor
                                   + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    MIN = min([*DF, floor])                         # [P22]
                    prev = len(DF)

                # 2) all up calls (served after the bottom reversal)
                if HC_up.size:                                      # [P21]
                    if DF and not HC_dw_1.size and HC_up.min() == MIN:
                        prev -= 1      # reversal floor is already a DF stop
                    stopsAt, prev = numOfCarStops(HC_up, Z, False, prev)
                    MIN = min(HC_up.min(), MIN)
                    WT[up_idx] = (((floor - MIN) + (HC_up - MIN)) * intFloor
                                  + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    if HC_dw_2.size:                                # [P22]
                        MAKS = HC_dw_2.max()

                # 3) down calls above the car (served after the top
                #    reversal)
                if HC_dw_2.size:
                    if not HC_up.size:
                        if DF and HC_dw_2.max() == MAKS:
                            prev -= 1
                    else:
                        MAKS = HC_dw_2.max()
                    stopsAt, prev = numOfCarStops(HC_dw_2, Z, True, prev)
                    WT[dw2_idx] = (((floor - MIN) + (MAKS - MIN)
                                    + (MAKS - HC_dw_2)) * intFloor
                                   + (stopsAt - 1) * stopOver)

        average[n] = WT.mean()

    return average
