"""
controller.py
=============
Python port of Controller.m - executes one simulation time step per
operate() call and delegates dispatching decisions to a decisionMaker.

decisionMaker interface contract (pinned down by this class; the
dispatcher ports - NearestCarDispatcher, GA, ACO, PSO, DE - must match):

    run(building, cars, HC, P)      assign waiting calls/passengers to
                                    cars (set .carId) and refresh each
                                    car's service lists
    updateCarStates(cars, stateUpdateType)
                                    update each car's movement state;
                                    stateUpdateType is 'fixed'|'flexible'
    stateUpdateTypeForNextDecision  attribute read by the controller
    setTraffic(traffic)             receive the active traffic pattern

Requirements on the Simulator port used with this class:
    simulator.time  current simulation time (advanced here, += Ts)
    simulator.Ts    simulation time step in seconds

Deviations from MATLAB ([E1]-[E2] inline):

  [E1] stopOverCounter countdown: MATLAB decrements by Ts and tests
       ~= 0. Exact zero is only reached when Ts divides the stop-over
       time exactly in floating point (true for Ts = 1 with integer
       door/transfer times). For any other Ts the counter skips zero
       and the ~=0 test keeps the car frozen forever. The port clamps
       the counter to 0 once it drops below a small epsilon - identical
       behaviour in the exact cases, no freeze otherwise. (Same latent
       float family as experiment.py [D4].)

  [E2] MATLAB incremented the waiting times of hall calls with a
       vectorized struct-array trick ([HC.waiting{dir}.WT] = deal(...));
       plain per-object loops produce the same result in Python.
"""
from __future__ import annotations

from typing import Any, List

_EPS = 1e-9


class Controller:
    """Port of the MATLAB Controller handle class."""

    def __init__(self, decisionMaker: Any) -> None:
        self.decisionMaker = decisionMaker

    def runDecisionProcess(self, building: Any, cars: List[Any],
                           HC: Any, P: Any) -> None:
        self.decisionMaker.run(building, cars, HC, P)

    def updateCarStatesForNextDecision(self, cars: List[Any]) -> None:
        self.decisionMaker.updateCarStates(
            cars, self.decisionMaker.stateUpdateTypeForNextDecision)

    def operate(self, cars: List[Any], simulator: Any, HC: Any, P: Any) -> None:
        """One simulation time step: transfers, movement, waiting times."""
        # Boarding/alighting at the current floors
        for car in cars:
            car.checkStopOver(HC, P, simulator.time)

        # Per-car movement for this time step
        for car in cars:
            if car.stopOverCounter != 0:
                # (a) the car is stopped (a passenger is entering or
                # leaving): count the stop-over timer back towards zero
                car.stopOverCounter -= simulator.Ts
                if car.stopOverCounter < _EPS:   # [E1] float-safe landing
                    car.stopOverCounter = 0.0
                # (MATLAB kept a commented-out block here that re-drew a
                # random parking floor for parkAlgorithm 3; preserved in
                # Controller.m, intentionally not ported.)
            elif (not isinstance(car.parkFloor, str)
                    and car.state == 0
                    and car.floor != car.parkFloor):
                # (b) idle with a parking floor configured: drift towards
                # it. NOTE (as in MATLAB): exact arrival requires
                # velocityFps * Ts to land on parkFloor exactly.
                car.park(simulator.Ts)
            elif car.state != 0:
                # (c) moving: update the position
                car.move(simulator.Ts)
            else:
                continue

        # Increment the waiting times of waiting calls/passengers [E2]
        # (dir 1: upwards, dir 2: downwards)
        for dir_ in (1, 2):
            for hallCall in HC.waiting[dir_]:
                hallCall.WT += simulator.Ts
            for passenger in P.waiting[dir_]:
                passenger.WT += simulator.Ts

        # Advance the simulation clock
        simulator.time = simulator.time + simulator.Ts

    def setTraffic(self, traffic: Any) -> None:
        self.decisionMaker.setTraffic(traffic)
