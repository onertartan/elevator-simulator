"""Exact, unlimited-capacity assignment for the Python destination/WT model.

For fixed snapshot parameters, car_waiting_times reads only one car and the
passengers in its assigned floor-direction calls. Other cars' assignments are
never read; passenger groups partition the waiting population. Thus the direct
objective is sum_j c_j(S_j) / P, even though routes depend on assigned sets and
all cars use 1 / cars[0].velocityFps. No monotonicity assumption is needed.

D(j,M) = min_{S subset M} [D(j-1,M xor S) + c_j(S)], including empty S,
enumerates every labelled call partition. Induction on j proves optimality
for this objective/assignment space when all layers finish. This is an exact
algorithm implemented in floating point, not a formal software proof or a
claim about dynamic-simulation optimality. Complexity: C*2**m cost entries,
O(C*3**m) transitions, two O(2**m) DP layers plus O(C*2**m) tables.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Callable

import numpy as np
from data_structures.passenger import WAITING_TIME_ENDPOINT

from decision.meta.obj_funs.obj_fun_destination import (
    car_waiting_times, objFunDestination,
)

OBJECTIVE_ID = "decision.meta.obj_funs.obj_fun_destination.objFunDestination"
SUCCESS_ATOL = 1e-9  # seconds; rtol is ALWAYS zero, never used for DP minima


def content_hash(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=lambda x: x.item()).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def objective_source_hashes() -> dict:
    root = Path(__file__).resolve().parent
    return {str(path.relative_to(root.parent)).replace("\\", "/"):
            hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), root / "meta/obj_funs/obj_fun_destination.py")}


def _integer(value, name: str, minimum: int = 0) -> int:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating))
            or not math.isfinite(value) or value != int(value) or value < minimum):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


class DestinationInstance:
    """Validated snapshot adapter shared by HC and the exact solver.

    Genes are ascending up-call floors then ascending down-call floors; one
    gene per (floor, direction), retaining every passenger destination. Public
    assignments are ZERO based. costs() is the sole 0 -> 1 conversion boundary.
    Capacity/load fields are deliberately not used to restrict assignments.
    door_opening_time defaults to zero for legacy programmatic snapshots;
    GUI/runtime callers supply the actual door-opening duration as physics
    metadata. WT ends at opening start: it is not an extra pickup cost.
    """

    def __init__(self, snapshot: dict, stop_over_time: float, velocity_fps: float,
                 *, door_opening_time: float = 0.0):
        self.n_floors = _integer(snapshot["n_floors"], "n_floors", 1)
        self.n_cars = _integer(snapshot["n_cars"], "n_cars", 1)
        if (not math.isfinite(velocity_fps) or velocity_fps <= 0
                or not math.isfinite(stop_over_time) or stop_over_time < 0):
            raise ValueError("velocity_fps must be positive; stop_over_time nonnegative")
        if not math.isfinite(door_opening_time) or door_opening_time < 0:
            raise ValueError("door_opening_time must be finite and nonnegative")
        for key in ("car_floor", "car_state", "car_df"):
            if len(snapshot[key]) != self.n_cars:
                raise ValueError(f"{key} must contain exactly n_cars entries")

        def floor_index(value):
            floor = _integer(value, "passenger/destination floor", 1)
            if floor > self.n_floors:
                raise ValueError("floor outside 1..n_floors")
            return floor

        waiting = {}
        for direction, key in ((1, "up"), (2, "dn")):
            waiting[direction] = []
            for floor, df in snapshot[key]:
                floor, df = floor_index(floor), floor_index(df)
                if (direction == 1 and df <= floor) or (direction == 2 and df >= floor):
                    raise ValueError("passenger destination contradicts call direction")
                waiting[direction].append(NS(floor=floor, DF=df))
        self.passengers = NS(waiting=waiting)
        self.n_passengers = sum(map(len, waiting.values()))
        if not self.n_passengers:
            raise ValueError("P=0: mean waiting time and optimum hit rate are undefined")
        up_calls = sorted({p.floor for p in waiting[1]})
        down_calls = sorted({p.floor for p in waiting[2]})
        self.hall_calls = up_calls + down_calls
        self.num_up_calls = len(up_calls)
        self.n_calls = len(self.hall_calls)
        self.call_order = [(f, "up") for f in up_calls] + [(f, "down") for f in down_calls]
        self.cars = []
        for floor, state, dfs in zip(snapshot["car_floor"], snapshot["car_state"],
                                     snapshot["car_df"]):
            if not math.isfinite(floor) or not 1 <= floor <= self.n_floors:
                raise ValueError("car floor outside 1..n_floors")
            if state not in (-1, 0, 1):
                raise ValueError("car state must be -1, 0 or 1")
            self.cars.append(NS(floor=float(floor), state=int(state),
                                DF={floor_index(df) for df in dfs},
                                stopOverTime=float(stop_over_time),
                                doorOpeningTime=float(door_opening_time),
                                velocityFps=float(velocity_fps)))
        # Stable passenger order matches the direct objective's sort.
        self._floors, self._dfs, self._bits = {}, {}, {}
        for d, calls, offset in ((1, up_calls, 0), (2, down_calls, len(up_calls))):
            passengers = sorted(waiting[d], key=lambda p: p.floor)
            indices = {f: k + offset for k, f in enumerate(calls)}
            self._floors[d] = np.array([p.floor for p in passengers], dtype=int)
            self._dfs[d] = np.array([p.DF for p in passengers], dtype=int)
            self._bits[d] = np.array([1 << indices[p.floor] for p in passengers],
                                     dtype=np.int64 if self.n_calls < 63 else object)

    def costs(self, chromosomes) -> np.ndarray:
        population = np.asarray(chromosomes)
        if population.ndim == 1:
            population = population.reshape(1, -1)
        if (population.ndim != 2 or population.shape[1] != self.n_calls
                or population.dtype.kind not in "iuf"
                or not np.isfinite(population).all()
                or (population != np.floor(population)).any()
                or (population < 0).any() or (population >= self.n_cars).any()):
            raise ValueError(f"expected {self.n_calls} integer car labels in 0..{self.n_cars - 1}")
        return objFunDestination(
            self.cars, self.hall_calls, self.num_up_calls,
            population.astype(np.int64) + 1, self.n_floors, self.passengers, "WT")

    def cost(self, chromosome) -> float:
        values = self.costs(chromosome)
        if len(values) != 1:
            raise ValueError("cost() expects exactly one assignment")
        return float(values[0])

    def fingerprint(self) -> str:
        """Bind a reference to model inputs AND the current Python semantics."""
        return content_hash({
            "objective": OBJECTIVE_ID, "mode": "WT", "capacity": "unlimited",
            "waiting_time_endpoint": WAITING_TIME_ENDPOINT,
            "n_floors": self.n_floors, "call_order": self.call_order,
            "passengers": {str(d): [(p.floor, p.DF) for p in self.passengers.waiting[d]]
                           for d in (1, 2)},
            "cars": [dict(floor=c.floor, state=c.state, DF=sorted(c.DF),
                          doorOpeningTime=c.doorOpeningTime,
                          stopOverTime=c.stopOverTime, velocityFps=c.velocityFps)
                     for c in self.cars],
            "source_sha256": objective_source_hashes(),
        })


def car_waiting_cost(car_index: int, call_mask: int, instance: DestinationInstance) -> float:
    """TOTAL assigned-passenger cost, not a car average or a masked global mean."""
    car_index = _integer(car_index, "car_index")
    call_mask = _integer(call_mask, "call_mask")
    if car_index >= instance.n_cars or call_mask >= 1 << instance.n_calls:
        raise ValueError("car index or call mask outside instance")
    if call_mask == 0:
        return 0.0
    up = (instance._bits[1] & call_mask) != 0
    down = (instance._bits[2] & call_mask) != 0
    wt_up, wt_down = car_waiting_times(
        instance.cars[car_index], instance._floors[1][up], instance._dfs[1][up],
        instance._floors[2][down], instance._dfs[2][down],
        1.0 / instance.cars[0].velocityFps)
    total = float(wt_up.sum() + wt_down.sum())
    if not math.isfinite(total) or total < 0:
        raise ValueError("invalid car-subset waiting cost")
    return total


@dataclass(frozen=True)
class ExactAssignmentResult:
    status: str
    message: str
    stage: str
    optimum_mean: float | None
    optimum_total: float | None
    assignment: tuple[int, ...] | None
    objective_recheck_mean: float | None
    problem_fingerprint: str | None
    cost_precompute_seconds: float
    dp_seconds: float
    verification_seconds: float
    total_seconds: float
    cost_entries_completed: int
    dp_transitions: int
    max_calls: int
    time_limit_seconds: float
    comparison_atol_seconds: float = SUCCESS_ATOL
    comparison_rtol: float = 0.0
    method: str = "subset_dynamic_programming"
    assignment_index_base: int = 0

    def to_dict(self):
        return asdict(self)


class _StopExact(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def solve_exact_assignment(
        instance: DestinationInstance, *, max_calls: int = 16,
        time_limit_seconds: float = 120.0,
        should_cancel: Callable[[], bool] | None = None,
        progress: Callable[[str, int, int], None] | None = None,
        ) -> ExactAssignmentResult:
    """Solve once; only a completed, directly re-evaluated DP is 'optimal'.

    Strict '<' determines minima (no hit tolerance). Submasks are visited in
    descending numeric order, so ties are deterministic. The first layer is
    c_0(M); only the full-set state of the last layer is needed. Neither shortcut
    discards a feasible partition. Cancellation is checked throughout both
    precomputation and DP, not just between entire car layers.
    """
    started = phase_started = time.perf_counter()
    stage = "validation"
    timings = dict(costs=0.0, dp=0.0, verification=0.0)
    entries = transitions = 0
    optimum = total = rechecked = assignment = fingerprint = None

    def set_stage(value):
        nonlocal stage, phase_started
        now = time.perf_counter()
        if stage in timings:
            timings[stage] += now - phase_started
        stage, phase_started = value, now

    def check():
        if should_cancel and should_cancel():
            raise _StopExact("cancelled", "Exact reference cancelled by user")
        if time.perf_counter() - started >= time_limit_seconds:
            raise _StopExact("time_limit", "Exact reference exceeded its time budget")

    try:
        max_calls = _integer(max_calls, "max_calls")
        time_limit_seconds = float(time_limit_seconds)
        if not math.isfinite(time_limit_seconds) or time_limit_seconds < 0:
            raise ValueError("time_limit_seconds must be finite and nonnegative")
        if instance.n_passengers <= 0 or instance.n_cars <= 0 or instance.n_calls <= 0:
            raise ValueError("nonempty cars, calls and waiting passengers are required")
        check()
        if instance.n_calls > max_calls:
            raise _StopExact("call_limit", f"{instance.n_calls} calls exceeds configured limit {max_calls}")
        fingerprint = instance.fingerprint()
        size = 1 << instance.n_calls
        full = size - 1
        set_stage("costs")
        costs = np.empty((instance.n_cars, size), dtype=float)
        for car in range(instance.n_cars):
            for mask in range(size):
                if mask % 64 == 0:
                    check()
                    if progress:
                        progress("costs", entries, instance.n_cars * size)
                costs[car, mask] = car_waiting_cost(car, mask, instance)
                entries += 1
        check()
        set_stage("dp")
        if progress:
            progress("dp", 0, instance.n_cars * size)
        check()
        choices = np.zeros((instance.n_cars, size), dtype=np.int64)
        choices[0] = np.arange(size)
        previous = costs[0].tolist()
        for car in range(1, instance.n_cars):
            last = car == instance.n_cars - 1
            current = [float("inf")] * size
            row = costs[car].tolist()
            masks = (full,) if last else range(size)
            for mask in masks:
                if mask % 256 == 0:
                    check()
                    if progress:
                        progress("dp", car * size + mask, instance.n_cars * size)
                best = float("inf")
                best_subset = 0
                subset = mask
                while True:
                    value = previous[mask ^ subset] + row[subset]
                    transitions += 1
                    if value < best:
                        best, best_subset = value, subset
                    if transitions % 4096 == 0:
                        check()
                    if subset == 0:
                        break
                    subset = (subset - 1) & mask
                current[mask] = best
                choices[car, mask] = best_subset
            previous = current
        check()
        set_stage("verification")
        total = float(previous[full])
        optimum = total / instance.n_passengers
        labels = [-1] * instance.n_calls
        remaining = full
        for car in range(instance.n_cars - 1, -1, -1):
            subset = int(choices[car, remaining])
            if subset & remaining != subset:
                raise _StopExact("inconsistent", "Traceback assigned a call twice")
            for call in range(instance.n_calls):
                if subset & (1 << call):
                    labels[call] = car
            remaining ^= subset
        if remaining or any(label < 0 for label in labels):
            raise _StopExact("inconsistent", "Incomplete optimum assignment traceback")
        assignment = tuple(labels)
        rechecked = instance.cost(assignment)
        if (not math.isfinite(total) or not math.isfinite(rechecked)
                or not np.isclose(rechecked, optimum, atol=SUCCESS_ATOL, rtol=0)):
            raise _StopExact("inconsistent", "DP and direct Python objective disagree")
        if fingerprint != instance.fingerprint():
            raise _StopExact("inconsistent", "Snapshot/objective changed during exact solve")
        check()
        status, message = "optimal", "Completed subset DP; assignment verified with direct objective"
        set_stage("complete")
    except _StopExact as exc:
        status, message = exc.status, exc.message
    except (ValueError, TypeError, OverflowError, KeyError, IndexError) as exc:
        status, message = "invalid_input", str(exc)
    except MemoryError:
        status, message = "resource_limit", "Insufficient memory for configured subset tables"
    ended = time.perf_counter()
    if stage in timings:
        timings[stage] += ended - phase_started
    if status != "optimal":
        # No unfinished or inconsistent value is exported as an optimum.
        optimum = total = assignment = rechecked = None
    return ExactAssignmentResult(
        status, message, stage, optimum, total, assignment, rechecked, fingerprint,
        timings["costs"], timings["dp"], timings["verification"], ended - started,
        entries, transitions, max_calls, time_limit_seconds)
