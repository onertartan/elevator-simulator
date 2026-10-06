"""
decision/decision_maker.py
===========================
Abstract base class for elevator decision-making logic.

CERTIFIED against matlab_src/decision/DecisionMaker.m (original
uploaded 2026-07): the constructor (stores
stateUpdateTypeForNextDecision only; availableInformation is commented
out in the original as well), updateCarServiceLists, and the abstract
run(building, cars, HC, P) signature all match the original.

Certified deviations:
  [P2] setTraffic: the original's method body is EMPTY (a stub for
       traffic-aware subclasses); the port stores self.traffic so that
       Dispatcher.run can forward it into dispatch() ([P11]) - a
       compatible superset, harmless for subclasses that ignore it.
  [P7] updateCarStates: the original loops bare
       cars(i).updateState(updateType) with NO list refresh - AND in
       the original Car.m the HC_above/HC_below properties read by the
       state==+/-1 branches are NEVER populated (declared [] and reset
       to [], but no assignment anywhere), so at runtime those
       branches reduce to the destination-floor test alone: a car that
       runs out of DFs always drops to idle and re-picks a direction
       via the case-0 refresh on its NEXT updateState call.
       The port instead has Car.updateState read the four MAINTAINED
       directional lists (HC_up_above + HC_down_above, ...), which is
       what the .m comments describe ("if an above call is not
       assigned to the car"), and refreshes them here before every
       updateState - without that refresh, stale lists hang the
       simulation (car climbs past the roof forever).
       !!! intent-faithful, not runtime-identical: a moving car with
       no DFs but assigned calls on BOTH sides keeps its direction in
       the port, while the original would bounce through idle and may
       choose the CLOSER side (case-0 logic). The smoke-test reference
       trip anchors the port's behavior.
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

        [P7] certified deviation: the original DecisionMaker.m loops
        bare updateState with no refresh (its above/below lists were
        never populated at all). The port refreshes the directional
        lists first - without this, stale lists hang the simulation.
        Full analysis in the module docstring."""
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
