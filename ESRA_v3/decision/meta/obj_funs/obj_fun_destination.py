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

  [P37] intFloor = 1/velocityFps = floorHeight/velocity - the
       dimensionally-correct inter-floor travel time (2 s at the GUI
       defaults: 3 m floors / 1.5 m/s), matching objFunConventional1
       [P37]. Deviation by decision (2026-08): objFunDestination.m
       line 22 still reads 1/velocity (m/s).
  [P38] Empty-prefix reversal: the first shared reversal-stop deduction
       in either direction requires prev > 0. With no previous stops,
       a pickup at the car's current floor must not acquire a negative
       stop offset. Counted shared stops still receive the deduction.
  [P39] WT ends when pickup doors START opening, not at boarding. No pickup
       opening duration is added. Earlier stops retain full stopOverTime,
       including opening/transfer/closing. The shared helper also serves
       exact/HC. Supersedes the former full-open pickup definition.
  [P41] State 0 denotes a direction-free car at this objective boundary.
       Evaluate both initial service directions and retain the complete route
       with lower TOTAL assigned-passenger WT; exact ties prefer UP. States
       +1/-1 keep their existing route. All direction choices are local:
       neither car.state nor the caller's inputs are changed. The two-array
       return contract is unchanged; applying a chosen direction in the
       simulator is outside this objective's scope.

MATLAB quirks preserved (flagged !!!):
  * Empty passenger sets and invalid call/assignment mappings now raise
    ValueError instead of returning NaN or silently leaving passengers at zero.
    The empty-prefix reversal correction is documented in [P38].
  * The former idle-as-down fall-through is superseded by [P41].
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


def car_waiting_times(car: Any, P1_floor: np.ndarray, P1_DF: np.ndarray,
                      P2_floor: np.ndarray, P2_DF: np.ndarray,
                      intFloor: float) -> Tuple[np.ndarray, np.ndarray]:
    """Destination/WT route calculation for ASSIGNED passengers only.

    State 0 is treated as direction-free: compare complete UP and DOWN routes
    by total assigned-passenger wait, retaining UP on an exact tie. The caller
    is responsible for supplying a consistent state; load/transfer eligibility
    is not inferred here. A signed state keeps its single existing route.

    Each candidate has independent stop counters and waiting arrays. Neither
    car.state nor passenger inputs are changed. Only the selected route's two
    waiting arrays are returned, not its direction. The caller supplies
    the snapshot-wide inter-floor time
    (1 / cars[0].velocityFps), NOT this individual car's speed. Capacity is not
    read. Returned arrays contain every assigned passenger, not unassigned
    zero-cost placeholders; summing them gives this car's TOTAL waiting cost.
    """
    if car.state != 0:
        return _car_waiting_times_for_direction(
            car, P1_floor, P1_DF, P2_floor, P2_DF, intFloor, direction=car.state)

    candidates = []
    for direction in (1, -1):
        candidates.append(_car_waiting_times_for_direction(
            car, P1_floor, P1_DF, P2_floor, P2_DF, intFloor, direction=direction))
    # min retains the first candidate on a tie. Select a WHOLE route, never
    # passenger-wise minima that would combine incompatible service orders.
    return min(candidates, key=lambda waits: float(waits[0].sum() + waits[1].sum()))


def _car_waiting_times_for_direction(
        car: Any, P1_floor: np.ndarray, P1_DF: np.ndarray,
        P2_floor: np.ndarray, P2_DF: np.ndarray, intFloor: float,
        *, direction: int) -> Tuple[np.ndarray, np.ndarray]:
    """Existing three-segment route for one explicit, local service direction.

    All per-route working state is initialized afresh. The [P38] shared-stop
    corrections and the [P39] opening-start waiting definition are unchanged.
    """
    if direction not in (-1, 1):
        raise ValueError("service direction must be 1 (up) or -1 (down)")
    WT1 = np.zeros(len(P1_floor))
    WT2 = np.zeros(len(P2_floor))
    floor = car.floor
    DF = sorted(car.DF)                         # [P19]
    stopOver = car.stopOverTime
    door_open = float(car.doorOpeningTime)
    if not np.isfinite(door_open) or door_open < 0:
        raise ValueError("doorOpeningTime must be finite and nonnegative")

    # Only passengers behind this car's assigned floor-direction calls enter
    # this calculation. No other car's assignment or load is read.
    up_all = np.ones(len(P1_floor), dtype=bool)
    up_1 = P1_floor >= floor
    up_2 = P1_floor < floor
    dw_all = np.ones(len(P2_floor), dtype=bool)
    dw_1 = P2_floor <= floor
    dw_2 = P2_floor > floor

    P_up_all_floor, P_up_all_DF = P1_floor[up_all], P1_DF[up_all]
    P_up_1_floor, P_up_1_DF = P1_floor[up_1], P1_DF[up_1]
    P_up_2_floor, P_up_2_DF = P1_floor[up_2], P1_DF[up_2]
    P_dw_all_floor, P_dw_all_DF = P2_floor[dw_all], P2_DF[dw_all]
    P_dw_1_floor, P_dw_1_DF = P2_floor[dw_1], P2_DF[dw_1]
    P_dw_2_floor, P_dw_2_DF = P2_floor[dw_2], P2_DF[dw_2]

    Z: List[int] = list(DF)    # consumed by the first segment
    prev = 0                   # stops accumulated so far

    # ================= CAR MOVING UP =======================
    if direction == 1:
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
            if prev > 0 and P_dw_all_floor.max() == MAKS:  # [P38]
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

    # ================= CAR MOVING DOWN =====================
    elif direction == -1:
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
            if prev > 0 and P_up_all_floor.min() == MINI:  # [P38]
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

    if (not np.isfinite(WT1).all() or not np.isfinite(WT2).all()
            or (WT1 < 0).any() or (WT2 < 0).any()):
        raise ValueError("destination/WT produced non-finite or negative waiting times")
    return WT1, WT2


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
    if not cars:
        raise ValueError("destination/WT requires at least one car")
    if (chrom.ndim != 2 or chrom.shape[1] != len(HC_arr)
            or chrom.dtype.kind not in "iuf" or not np.isfinite(chrom).all()
            or (chrom != np.floor(chrom)).any()
            or (chrom < 1).any() or (chrom > len(cars)).any()):
        raise ValueError("assignments must have one integer car label (1..C) per call")
    if (not isinstance(HC_numofups, (int, np.integer))
            or not 0 <= HC_numofups <= len(HC_arr)):
        raise ValueError("invalid up-call count")
    up_calls, down_calls = HC_arr[:HC_numofups], HC_arr[HC_numofups:]
    if (len(set(up_calls)) != len(up_calls)
            or len(set(down_calls)) != len(down_calls)
            or set(up_calls) != set(P1_floor) or set(down_calls) != set(P2_floor)):
        raise ValueError("calls must match waiting passenger floor-direction groups exactly")
    if len(P1_floor) + len(P2_floor) == 0:
        raise ValueError("mean waiting time is undefined without waiting passengers")
    if (not np.isfinite(cars[0].velocityFps) or cars[0].velocityFps <= 0
            or any(not np.isfinite(c.stopOverTime) or c.stopOverTime < 0 for c in cars)):
        raise ValueError("invalid destination/WT time parameters")
    intFloor = 1.0 / cars[0].velocityFps    # [P37] floorHeight/velocity
    average = np.zeros(chrom.shape[0])

    for n in range(chrom.shape[0]):
        WT1 = np.zeros(len(P1_floor))    # per up-waiting passenger
        WT2 = np.zeros(len(P2_floor))    # per down-waiting passenger

        for label, car in enumerate(cars, start=1):
            HC_up = HC_arr[:HC_numofups][chrom[n, :HC_numofups] == label]
            HC_dw = HC_arr[HC_numofups:][chrom[n, HC_numofups:] == label]
            up = np.isin(P1_floor, HC_up)
            down = np.isin(P2_floor, HC_dw)
            WT1[up], WT2[down] = car_waiting_times(
                car, P1_floor[up], P1_DF[up], P2_floor[down], P2_DF[down],
                intFloor)

        combined = np.concatenate([WT1, WT2])
        average[n] = (combined.mean() if combined.size
                      else float("nan"))    # !!! MATLAB mean([]) = NaN

    return average
