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
