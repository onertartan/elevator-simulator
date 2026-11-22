"""
decision/dispatcher.py
=======================
Abstract base class for dispatching logic, extending DecisionMaker.
(User's conversion of Dispatcher.m, with fixes [P3]-[P4].)

CERTIFIED against matlab_src/decision/Dispatcher.m (original uploaded
2026-07): run()'s ordering matches the original exactly -
dispatch -> updateCarServiceLists -> updateCarStates(
stateUpdateTypeForNextDecision). (The .m source comment records that a
hardcoded 'fixed' was once replaced by the property - the port uses
the property, matching the final original.)

  [P11] certified deviation: the original calls
       dispatch(building, cars, HC, P) with NO traffic argument (and
       the base setTraffic is an empty stub - see [P2]). The port
       forwards self.traffic as a 5th argument that current
       subclasses accept as traffic=None and ignore - a compatible
       superset kept for traffic-aware subclasses (e.g. MDP).

NOTE (physics-relevant, CERTIFIED against the original): run()
updates car states as its step 3, IN ADDITION to Controller's
per-tick updateCarStatesForNextDecision after operate. A freshly
assigned car therefore starts moving in the SAME tick it is
dispatched, exactly as in Dispatcher.m. The test suite's reference
trip reflects this (boarding at t=2).

  [A6] assign_call(): the single place that writes carId to a hall call
       and its waiting passengers. Passengers a car has already accepted
       for boarding (doorOpeningStartTime set, i.e. they sit in that
       car's pendingBoard while the doors open) keep their accepting
       car. Before [A6] every dispatcher rewrote carId for ALL waiting
       passengers at the call floor, so a new same-floor/same-direction
       call registered during the 2 s door-opening window could hand
       accepted passengers to a second car; both cars then boarded them
       (duplicate rows in P.served - see RUNNING.md section 11).
"""
from abc import abstractmethod
from typing import Any, List

from building import Building
from car import Car
from data_structures import HallCallLists, PassengerLists
from .decision_maker import DecisionMaker


class Dispatcher(DecisionMaker):
    """Abstract base class for dispatching logic, extending DecisionMaker."""

    @abstractmethod
    def dispatch(self, building: Building, cars: List[Car], HC: HallCallLists, P: PassengerLists,
                 traffic: Any = None) -> None:
        """Calculate Figures of Suitability (FS) and assign calls to cars."""

    @staticmethod
    def assign_call(hall_call: Any, dir_: int, car_id: int, P: PassengerLists) -> int:
        """[A6] Assign a waiting hall call and the waiting passengers it
        covers (same floor, same direction) to car_id.

        Passengers already accepted by a car for boarding (their
        doorOpeningStartTime is set) are left with their accepting car:
        the pickup has physically started and the car will board them
        when its doors are open. Returns the number of such passengers
        that were skipped. Every dispatcher must write carId through
        this helper so the rule lives in one place.
        """
        hall_call.carId = car_id
        skipped = 0
        for passenger in P.waiting[dir_]:
            if passenger.floor != hall_call.floor:
                continue
            if getattr(passenger, "doorOpeningStartTime", None) is not None:
                skipped += 1
                continue
            passenger.carId = car_id
        return skipped

    def run(self, building: Any, cars: List[Car], HC: HallCallLists, P: PassengerLists) -> None:
        """
        Main simulation step for the dispatcher:
        1. Dispatch cars (assign calls).
        2. Update car service lists.
        3. Update car states based on configuration.
        """
        self.dispatch(building, cars, HC, P, self.traffic)      # [P4]
        self.update_car_service_lists(cars, HC, P)
        self.update_car_states(cars, self.state_update_type_for_next_decision)
