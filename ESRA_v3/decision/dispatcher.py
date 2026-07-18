"""
decision/dispatcher.py
=======================
Abstract base class for dispatching logic, extending DecisionMaker.
(User's conversion of Dispatcher.m, with fixes [P3]-[P4].)


  [P11] run() forwards self.traffic into dispatch(), matching the
       trailing `~` parameter that NearestCarDispatcher.m ignores.
       Will it be necessary in any subclass?

NOTE (physics-relevant, kept from the user's Dispatcher.m conversion):
run() updates car states as its step 3, IN ADDITION to Controller's
per-tick updateCarStatesForNextDecision after operate. A freshly
assigned car therefore starts moving in the SAME tick it is dispatched.
The test suite's reference trip reflects this (boarding at t=2).
Upload Dispatcher.m to certify this ordering against the original.
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
