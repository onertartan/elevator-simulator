"""
decision/meta/obj_funs/obj_fun_destination.py
==============================================
Port of matlab_src/objFuns/objFunDestination.m - the destination-aware
estimated-waiting-time objective for the metaheuristic dispatchers.

objFunConventional1 sees only hall-call FLOORS; this objective walks
the waiting PASSENGERS: every passenger's boarding floor AND
destination floor (Passenger.DF) enter the car's stop sequence, so the
estimated stop count includes the intermediate stops the car will make
to deliver the passengers it collects along the route.

For every chromosome row (one car label per hall call, up calls first
then down calls - the [P17] encoding), each car's route is walked in
three direction segments; every waiting passenger assigned to the car
(floor-matched against the car's hall calls) gets

    WT = travel_time_to_boarding_floor + stops_before_boarding * stopOverTime

with stops ranked by numOfCarStopsTrue over boarding floors, passenger
destinations and committed car destinations. The row cost is the mean
WT over ALL waiting passengers of both directions (lower = better).
Plugs into startData.objFun with the [P13] wrapper signature:
objFun(cars_copy, HC_all, HC_numofups, population, nf, P, "WT");
P is the live PassengerLists - read-only here, never mutated.

Deviation notes (continuing the [P#] family):

  [P32] Passenger snapshot: MATLAB sorts [P.waiting{d}.floor] and
       scatters [P.waiting{d}.DF] through the sort permutation
       (objFunDestination.m lines 3-19). The port takes one stable
       argsort over the registration-order waiting lists
       (PassengerLists.add appends - see [P17]): same floor/DF
       alignment, ties keep registration order exactly like MATLAB's
       stable sort.
  [P33] numOfCarStopsTrue ports NumofCSTrue.m (from ESRA_v2/objFuns,
       copied into matlab_src/objFuns for reference). Stop floors =
       unique(boarding floors + passenger DFs + car DFs); the
       per-element find() scans become one {floor: rank} dict per
       segment. Both rank vectors (at boarding floor / at destination
       floor) are returned; the WT path consumes only the former, the
       destination ranks serve the future JT port.
  [P34] MATLAB min([])/max([]) yield [] and `x == []` is [] (falsy):
       here MINI/MAKS are None when their source set is empty, the
       reversal corrections check `is not None` first, and the min/max
       folds drop the None - each value is only read in branches where
       the .m source guarantees it is defined.
  [P35] Only optimizationParameter == "WT" is implemented. In the .m
       source the "JT" nested function stores its result in a LOCAL
       `TOTAL` (nested-function scoping), so AVERAGE is returned
       all-zeros; the "CTT" nested function reads WT1/WT2 that are
       undefined in its scope (MATLAB runtime error). Rather than
       silently optimizing a zero vector, the port raises
       NotImplementedError for both - the [P13] wrapper only ever
       passes "WT".

MATLAB quirks preserved (flagged !!!):
  * !!! intFloor = 1/cars(1).velocity with velocity in m/s - same
    quirk as the objFunConventional1 port; the dimensionally-correct
    inter-floor time would be 1/velocityFps. Kept for identical costs.
  * !!! mean([WT1 WT2]) over zero waiting passengers is NaN, as in
    MATLAB (unreachable via dispatch(), which returns early when no
    hall calls exist).
  * A passenger whose floor matches no hall call assigned to any car
    keeps WT = 0 and still enters the mean, as in MATLAB.
  * Unlike objFunConventional1 there is NO idle-direction decision:
    idle cars (state 0) fall through to the state~=1 branch and the
    car copies are never mutated.
"""
from __future__ import annotations

from typing import Any, List, Sequence, Tuple

import numpy as np


def numOfCarStopsTrue(pFloors: Sequence[int], pDFs: Sequence[int],
                      carDF: Sequence[int], reverse: bool,
                      numStopsPrevious: int
                      ) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    [P33] Port of NumofCSTrue.m: rank every passenger boarding floor
    and destination floor within this direction segment's stop
    sequence (boarding floors + passenger destinations + committed car
    destinations), offset by the stops already accumulated in earlier
    segments. pFloors and pDFs are aligned per passenger.

    Returns (stops_at_boarding_floor, stops_at_DF, stops_in_segment).
    """
    stopFloors = sorted(set(pFloors) | set(pDFs) | set(carDF))
    if reverse:                       # car serves this segment downwards
        stopFloors.reverse()
    rank = {floor: k for k, floor in enumerate(stopFloors, start=1)}
    stopsAtFloor = np.array([rank[floor] + numStopsPrevious
                             for floor in pFloors])
    stopsAtDF = np.array([rank[df] + numStopsPrevious for df in pDFs])
    return stopsAtFloor, stopsAtDF, len(stopFloors)


def _sortedWaiting(passengers: Sequence[Any]
                   ) -> Tuple[np.ndarray, np.ndarray]:
    """[P32] (floors, DFs) of one waiting list, floor-sorted stably -
    MATLAB's sort([P.waiting{d}.floor]) plus the DF scatter."""
    floors = np.array([p.floor for p in passengers], dtype=int)
    dfs = np.array([p.DF for p in passengers], dtype=int)
    order = np.argsort(floors, kind="stable")
    return floors[order], dfs[order]


def objFunDestination(cars: List[Any], HC: Sequence[int],
                      HC_numofups: int, chrom: Any, nf: int,
                      P: Any, optimizationParameter: str = "WT"
                      ) -> np.ndarray:
    """
    objFunDestination(cars, HC, HC_numofups, chrom, nf, P, "WT")

    cars:          per-call deep copies of the fleet ([P14]; read-only
                   here - this objective never writes car state)
    HC:            all waiting hall-call floors, up calls then down
    HC_numofups:   how many leading entries of HC are up calls
    chrom:         (nPop, len(HC)) car labels 1..len(cars)
    nf:            number of floors (unused by the WT path; kept for
                   the [P13] signature)
    P:             PassengerLists - waiting[1]/waiting[2] are read
    optimizationParameter: only "WT" is ported ([P35])

    Returns the per-row mean estimated waiting time over all waiting
    passengers, shape (nPop,).
    """
    if optimizationParameter != "WT":
        raise NotImplementedError(
            f"objFunDestination: optimizationParameter "
            f"'{optimizationParameter}' is not ported - the MATLAB "
            "source returns all-zeros for 'JT' (result assigned to a "
            "local TOTAL) and errors for 'CTT' (undefined WT1/WT2); "
            "only 'WT' is meaningful. [P35]")

    chrom = np.asarray(chrom)
    HC_arr = np.asarray(HC, dtype=int)   # floor numbers, 1..nf
    P1_floor, P1_DF = _sortedWaiting(P.waiting[1])     # up-waiting
    P2_floor, P2_DF = _sortedWaiting(P.waiting[2])     # down-waiting
    intFloor = 1.0 / cars[0].velocity          # !!! m/s quirk, see top
    average = np.zeros(chrom.shape[0])

    for n in range(chrom.shape[0]):
        WT1 = np.zeros(len(P1_floor))    # per up-waiting passenger
        WT2 = np.zeros(len(P2_floor))    # per down-waiting passenger

        for label, car in enumerate(cars, start=1):
            floor = car.floor
            DF = sorted(car.DF)                         # [P19]
            stopOver = car.stopOverTime

            # Hall calls this chromosome row assigns to this car,
            # split into the three route segments.
            HC_up = HC_arr[:HC_numofups][chrom[n, :HC_numofups] == label]
            HC_up_1 = HC_up[HC_up >= floor]    # up calls at/above car
            HC_up_2 = HC_up[HC_up < floor]     # up calls below car
            HC_dw = HC_arr[HC_numofups:][chrom[n, HC_numofups:] == label]
            HC_dw_1 = HC_dw[HC_dw <= floor]    # down calls at/below
            HC_dw_2 = HC_dw[HC_dw > floor]     # down calls above

            # Waiting passengers behind those calls: boolean masks
            # (MATLAB ismember) over the sorted [P32] snapshots.
            up_all = np.isin(P1_floor, HC_up)
            up_1 = np.isin(P1_floor, HC_up_1)
            up_2 = np.isin(P1_floor, HC_up_2)
            dw_all = np.isin(P2_floor, HC_dw)
            dw_1 = np.isin(P2_floor, HC_dw_1)
            dw_2 = np.isin(P2_floor, HC_dw_2)

            P_up_all_floor, P_up_all_DF = P1_floor[up_all], P1_DF[up_all]
            P_up_1_floor, P_up_1_DF = P1_floor[up_1], P1_DF[up_1]
            P_up_2_floor, P_up_2_DF = P1_floor[up_2], P1_DF[up_2]
            P_dw_all_floor, P_dw_all_DF = P2_floor[dw_all], P2_DF[dw_all]
            P_dw_1_floor, P_dw_1_DF = P2_floor[dw_1], P2_DF[dw_1]
            P_dw_2_floor, P_dw_2_DF = P2_floor[dw_2], P2_DF[dw_2]

            Z: List[int] = list(DF)    # consumed by the first segment
            prev = 0                   # stops accumulated so far

            # ================= CAR MOVING UP =======================
            if car.state == 1:
                MINI = (P_dw_all_DF.min()
                        if P_dw_all_DF.size else None)          # [P34]
                MAKS = max([*P_up_1_DF, floor, *DF])

                # 1) up passengers at/above the car
                if P_up_1_floor.size:
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_up_1_floor, P_up_1_DF, Z, False, prev)
                    WT1[up_1] = ((P_up_1_floor - floor) * intFloor
                                 + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    prev = len(DF)

                # 2) all down passengers (served after the top
                #    reversal)
                if P_dw_all_floor.size:
                    if P_dw_all_floor.max() == MAKS:
                        prev -= 1   # reversal floor already counted
                    MAKS = max(MAKS, P_dw_all_floor.max())
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_dw_all_floor, P_dw_all_DF, Z, True, prev)
                    WT2[dw_all] = ((MAKS - floor + MAKS - P_dw_all_floor)
                                   * intFloor + (stopsAt - 1) * stopOver)
                    Z = []

                # 3) up passengers below the car (served after the
                #    bottom reversal)
                if P_up_2_floor.size:
                    if MINI is not None and P_up_2_floor.min() == MINI:
                        prev -= 1                               # [P34]
                    MINI = (min([MINI, *P_up_2_floor])
                            if MINI is not None else P_up_2_floor.min())
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_up_2_floor, P_up_2_DF, Z, False, prev)
                    WT1[up_2] = (((MAKS - floor) + (MAKS - MINI)
                                  + (P_up_2_floor - MINI)) * intFloor
                                 + (stopsAt - 1) * stopOver)

            # ============ CAR MOVING DOWN (or idle) ================
            if car.state != 1:
                MAKS = (P_up_all_DF.max()
                        if P_up_all_DF.size else None)          # [P34]
                MINI = min([*P_dw_1_DF, floor, *DF])

                # 1) down passengers at/below the car
                if P_dw_1_floor.size:
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_dw_1_floor, P_dw_1_DF, Z, True, prev)
                    WT2[dw_1] = ((floor - P_dw_1_floor) * intFloor
                                 + (stopsAt - 1) * stopOver)
                    Z = []
                else:
                    prev = len(DF)

                # 2) all up passengers (served after the bottom
                #    reversal)
                if P_up_all_floor.size:
                    if P_up_all_floor.min() == MINI:
                        prev -= 1   # reversal floor already counted
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_up_all_floor, P_up_all_DF, Z, False, prev)
                    MINI = min(P_up_all_floor.min(), MINI)
                    WT1[up_all] = (((floor - MINI)
                                    + (P_up_all_floor - MINI)) * intFloor
                                   + (stopsAt - 1) * stopOver)
                    Z = []

                # 3) down passengers above the car (served after the
                #    top reversal)
                if P_dw_2_floor.size:
                    if MAKS is not None and P_dw_2_floor.max() == MAKS:
                        prev -= 1                               # [P34]
                    MAKS = (max([MAKS, *P_dw_2_floor])
                            if MAKS is not None else P_dw_2_floor.max())
                    stopsAt, _, prev = numOfCarStopsTrue(
                        P_dw_2_floor, P_dw_2_DF, Z, True, prev)
                    WT2[dw_2] = (((floor - MINI) + (MAKS - MINI)
                                  + (MAKS - P_dw_2_floor)) * intFloor
                                 + (stopsAt - 1) * stopOver)

        combined = np.concatenate([WT1, WT2])
        average[n] = (combined.mean() if combined.size
                      else float("nan"))    # !!! MATLAB mean([]) = NaN

    return average
