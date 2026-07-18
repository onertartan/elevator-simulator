"""
decision/decision_maker.py
===========================
Abstract base class for elevator decision-making logic.
"""
from abc import ABC, abstractmethod
from typing import Any, List


class DecisionMaker(ABC):
    """Abstract base class for elevator decision-making logic."""

    def __init__(self, start_data: Any):
        # [P1] canonical (Controller contract) storage:
        self.stateUpdateTypeForNextDecision: str = (
            start_data.stateUpdateTypeForNextDecision)
        self.traffic: Any = None          # [P2]

    # ---- snake_case API (user's conversion style) -----------------------
    @property
    def state_update_type_for_next_decision(self) -> str:      # [P1]
        return self.stateUpdateTypeForNextDecision

    @state_update_type_for_next_decision.setter
    def state_update_type_for_next_decision(self, value: str) -> None:
        self.stateUpdateTypeForNextDecision = value

    @abstractmethod
    def run(self, building: Any, cars: List[Any], HC: Any, P: Any) -> None:
        """Execute the decision-making cycle."""

    def update_car_states(self, cars: List[Any], update_type: str) -> None:
        """Update states for all cars based on the given update type.

        [P7] car.updateAboveBelowHCs() restored before updateState: the
        state==+/-1 branches of Car.updateState read the CACHED
        above/below hall-call lists (only the idle branch refreshes
        them). Without this per-tick refresh, a car whose call was just
        picked up keeps a stale 'call above' and climbs past the roof
        forever (reproduced as an infinite simulation loop). Verify the
        call exists in DecisionMaker.m."""
        for car in cars:
            car.updateAboveBelowHCs()          # [P7]
            car.updateState(update_type)

    def update_car_service_lists(self, cars: List[Any],
                                 HC: Any, P: Any) -> None:
        """Update assigned service lists for all cars."""
        for car in cars:
            car.updateServiceList(HC, P)

    def set_traffic(self, traffic: Any) -> None:
        """Store traffic information for use by dispatch(). [P2]"""
        self.traffic = traffic

    # ---- camelCase adapters (Controller.m contract) [P1] -----------------
    def updateCarStates(self, cars: List[Any], update_type: str) -> None:
        self.update_car_states(cars, update_type)

    def setTraffic(self, traffic: Any) -> None:
        self.set_traffic(traffic)
