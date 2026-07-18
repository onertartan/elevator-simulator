"""
decision/nearest_car_dispatcher.py
===================================
Nearest Car dispatcher (user's conversion of NearestCarDispatcher.m,
with fixes [P5]-[P6]).

  [P5] `from data_structures.HallCall import HallCall` -> the module is
       `hall_call` (see car.py's imports); the CapCase form only worked
       on case-insensitive filesystems. `from car import Car` moved
       under TYPE_CHECKING so the decision package does not pull PySide6
       at import time (Car is only used as a type hint here).
  [P6] dispatch accepts the (unused) traffic argument, mirroring the
       trailing `~` in NearestCarDispatcher.m and the base run() call.

Kept from the user's port, previously reviewed: carId is set to
cars[j].id rather than MATLAB's raw loop index (identical results, ids
are 1..N); the tie-break compares SIGNED distances - a MATLAB quirk
that prefers the car ABOVE the call among equally suitable ones.
"""
from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

from data_structures.hall_call import HallCall            # [P5]
from .dispatcher import Dispatcher

if TYPE_CHECKING:                                          # [P5]
    from car import Car


class NearestCarDispatcher(Dispatcher):
    """
    Nearest Car Dispatcher implementation computing Figure of
    Suitability (FS) to dispatch elevator cars efficiently.
    """

    def __init__(self, start_data: Any):
        super().__init__(start_data)
        # Store figures of suitability per direction (1: up, 2: down)
        self.FS: Dict[int, List[List[float]]] = {1: [], 2: []}

    def dispatch(self, building: Any, cars: List[Any], HC: Any, P: Any,
                 traffic: Any = None) -> None:             # [P6]
        """Calculate FS and assign waiting calls (and corresponding
        passengers) to cars."""
        self.FS = {1: [], 2: []}

        for dir_ in (1, 2):
            waiting_calls = HC.waiting[dir_]
            num_of_hcs = len(waiting_calls)
            num_of_cars = len(cars)
            if num_of_hcs == 0:
                continue

            # f: Figure of suitability matrix [num_of_hcs x num_of_cars]
            f = [[0.0] * num_of_cars for _ in range(num_of_hcs)]
            # assigned_cars tracks the best car index for each call
            assigned_cars = [0] * num_of_hcs

            for i, hall_call in enumerate(waiting_calls):
                fmax = -1.0
                for j, car in enumerate(cars):
                    d = hall_call.floor - car.floor
                    f[i][j] = self.calculate_fs(hall_call, car,
                                                building.nf, d)
                    # Determine best car based on highest FS, resolving ties
                    if f[i][j] > fmax:
                        assigned_cars[i] = j
                        fmax = f[i][j]
                    elif f[i][j] == fmax:
                        d_assigned = (hall_call.floor
                                      - cars[assigned_cars[i]].floor)
                        if d < d_assigned:
                            assigned_cars[i] = j
                        elif (d == d_assigned
                              and car.stopOverCounter
                              < cars[assigned_cars[i]].stopOverCounter):
                            assigned_cars[i] = j

            # Apply assigned car IDs to hall calls and associated passengers
            for i, hall_call in enumerate(waiting_calls):
                best_car_id = cars[assigned_cars[i]].id
                hall_call.carId = best_car_id
                for passenger in P.waiting[dir_]:
                    if passenger.floor == hall_call.floor:
                        passenger.carId = best_car_id

            self.FS[dir_] = f

    def calculate_fs(self, hall_call: HallCall, car: "Car",
                     nf: int, d: float) -> float:
        """Calculate the Figure of Suitability (FS) of a car for a
        specific hall call."""
        def sign(x: float) -> int:
            return 1 if x > 0 else -1 if x < 0 else 0

        # Car is moving away
        if (sign(d) * car.state == -1
                or (d == 0 and car.state * hall_call.direction == -1)):
            fs = 1.0
        # Car and call have the same direction (car is approaching)
        elif car.state == hall_call.direction:
            fs = nf + 1 - abs(d)
        # Opposite directions but approaching, or the car is idle
        else:
            fs = nf - abs(d)
        return float(fs)
