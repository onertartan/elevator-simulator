"""Simulation adapter for the exact, unlimited-capacity destination/WT model.

The solver stays in exact_assignment.py. This class snapshots the live state,
solves it and applies a completed assignment; Dispatcher.run() then refreshes
service lists and movement states as it does for other dispatchers. Optimality
is for estimated mean PASSENGER waiting time, not measured simulation waiting
time. No capacity pruning, GA fallback or HC difficulty evaluation is added.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable

from .dispatcher import Dispatcher
from .exact_assignment import (
    DestinationInstance, ExactAssignmentResult, _integer, solve_exact_assignment,
)
from .meta.obj_funs import objFunDestination


class ExactDispatchError(RuntimeError):
    """A non-optimal solve must not apply partial assignments."""

    def __init__(self, result: ExactAssignmentResult):
        self.result = result
        super().__init__(
            f"ExactDispatcher: {result.status} during {result.stage} "
            f"after {result.total_seconds:.3f} s. {result.message}. "
            "No call or passenger assignments were changed.")


class ExactDispatchCancelled(ExactDispatchError):
    """Normal user cancellation; the GUI worker need not show an error dialog."""


class ExactDispatcher(Dispatcher):
    """Exact assignment of waiting floor-direction calls to actual car IDs.

    start_data: stateUpdateTypeForNextDecision ('fixed'), optionally
    exactMaxCalls (16) and exactTimeLimitSeconds (120). Objective is fixed to
    objFunDestination/WT. last_result contains the zero-based assignment,
    objective optimum and timings; last_call_order identifies its genes.

    Prefer a static one-shot run with no new arrivals. Each repeated decision
    solves a fresh snapshot and can be expensive. A snapshot during pending
    boarding is rejected: its passengers still wait after the hall call has
    been answered and do not form the solver's original call-based problem.
    Simulation capacities and transfer timing are never changed here.
    """

    def __init__(self, start_data, *, should_cancel: Callable[[], bool] | None = None,
                 progress: Callable[[str, int, int], None] | None = None):
        super().__init__(start_data)
        if self.stateUpdateTypeForNextDecision != "fixed":
            raise ValueError("ExactDispatcher requires fixed collective-control state updates")
        if getattr(start_data, "objectiveFunction", "Destination Information") != "Destination Information":
            raise ValueError("ExactDispatcher supports only Destination Information / WT")
        if getattr(start_data, "objFun", objFunDestination) is not objFunDestination:
            raise ValueError("ExactDispatcher supports only the Python objFunDestination / WT")
        self.max_calls = _integer(getattr(start_data, "exactMaxCalls", 16), "exactMaxCalls", 1)
        self.time_limit_seconds = float(getattr(start_data, "exactTimeLimitSeconds", 120.0))
        if not math.isfinite(self.time_limit_seconds) or self.time_limit_seconds < 0:
            raise ValueError("exactTimeLimitSeconds must be finite and nonnegative")
        self.should_cancel = should_cancel
        self.progress = progress
        self.last_result: ExactAssignmentResult | None = None
        self.last_call_order: list[tuple[int, str]] = []
        self.last_status = "not_run"

    @staticmethod
    def _snapshot(building, cars, HC, P):
        if not cars:
            raise ValueError("ExactDispatcher requires at least one car")
        car_ids = [_integer(car.id, "car ID", 1) for car in cars]
        if len(set(car_ids)) != len(car_ids):
            raise ValueError("ExactDispatcher requires unique car IDs")
        if any(getattr(car, "pendingBoard", ()) for car in cars):
            raise ValueError(
                "ExactDispatcher cannot reassign a snapshot during pending boarding. "
                "Use one-shot dispatch with no new arrivals; transfer timing is unchanged.")
        call_by_key = {}
        for direction, name in ((1, "up"), (2, "down")):
            for call in HC.waiting[direction]:
                if call.direction != direction:
                    raise ValueError("Hall-call direction does not match its waiting list")
                key = (call.floor, name)
                if key in call_by_key:
                    raise ValueError("Duplicate floor-direction hall call")
                call_by_key[key] = call
            if any(p.direction != direction for p in P.waiting[direction]):
                raise ValueError("Passenger direction does not match its waiting list")
        snapshot = dict(
            n_floors=building.nf, n_cars=len(cars),
            car_floor=[car.floor for car in cars],
            car_state=[car.state for car in cars],
            car_df=[sorted(car.DF) for car in cars],
            up=[(p.floor, p.DF) for p in P.waiting[1]],
            dn=[(p.floor, p.DF) for p in P.waiting[2]])
        instance = DestinationInstance(snapshot, cars[0].stopOverTime, cars[0].velocityFps,
                                       door_opening_time=cars[0].doorOpeningTime)
        if set(instance.call_order) != set(call_by_key):
            raise ValueError("Waiting hall calls and passenger floor-direction groups do not match")
        # The snapshot constructor accepts homogeneous physics. Preserve any
        # per-car differences in the actual live state without copying mutable
        # simulation objects. The objective still uses the FIRST car's speed.
        for captured, live in zip(instance.cars, cars):
            if not math.isfinite(live.stopOverTime) or live.stopOverTime < 0:
                raise ValueError("Invalid car stop-over time")
            if not math.isfinite(live.velocityFps) or live.velocityFps <= 0:
                raise ValueError("Invalid car velocityFps")
            if not math.isfinite(live.doorOpeningTime) or live.doorOpeningTime < 0:
                raise ValueError("Invalid car doorOpeningTime")
            captured.stopOverTime = float(live.stopOverTime)
            captured.doorOpeningTime = float(live.doorOpeningTime)
            captured.velocityFps = float(live.velocityFps)
        return instance, call_by_key, car_ids

    def dispatch(self, building, cars, HC, P, traffic=None) -> None:
        self.last_result = None
        self.last_call_order = []
        self.last_status = "no_calls"
        if not HC.waiting[1] and not HC.waiting[2]:
            return
        self.last_status = "invalid_input"
        instance, call_by_key, car_ids = self._snapshot(building, cars, HC, P)
        self.last_call_order = list(instance.call_order)
        self.last_status = "solving"
        result = solve_exact_assignment(
            instance, max_calls=self.max_calls, time_limit_seconds=self.time_limit_seconds,
            should_cancel=self.should_cancel, progress=self.progress)
        self.last_result = result
        self.last_status = result.status
        if result.status == "cancelled":
            raise ExactDispatchCancelled(result)
        if result.status != "optimal":
            raise ExactDispatchError(result)

        if self.should_cancel and self.should_cancel():
            self.last_result = replace(
                result, status="cancelled", stage="application",
                message="Cancelled before applying the completed assignment",
                optimum_mean=None, optimum_total=None, assignment=None,
                objective_recheck_mean=None)
            self.last_status = "cancelled"
            raise ExactDispatchCancelled(self.last_result)

        # Nothing live is mutated until the entire assignment has passed
        # validation. Map by (floor, direction), not incidental list position.
        instance.cost(result.assignment)  # validates length, integer labels and range
        assignments = {key: car_ids[label]
                       for key, label in zip(instance.call_order, result.assignment)}
        for key, call in call_by_key.items():
            call.carId = assignments[key]
        for direction, name in ((1, "up"), (2, "down")):
            for passenger in P.waiting[direction]:
                passenger.carId = assignments[(passenger.floor, name)]
