from __future__ import annotations
from PySide6.QtGui import QColor
from typing import Any, List, Optional, Sequence, TYPE_CHECKING

from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger_lists import PassengerLists

if TYPE_CHECKING:
    # For type hints only; avoids circular imports at runtime
    from data_structures.hall_call_lists import HallCallLists as _HallCallLists
    from data_structures.passenger_lists import PassengerLists as _PassengerLists


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


class Car:
    """
    Python adaptation of the Car class.

    MATLAB-specific changes:
    - Persistent state in colors() is implemented via a class attribute; indexing is adapted to Python (1-based -> 0-based).
    - Numeric types use Python int/float; int8 semantics are not strictly enforced but values remain integral where applicable.
    - MATLAB cell/array operations map to Python lists and dicts keyed by direction (1: up/same, 2: down).
    """

    # Static color set (initialized on first use)
    # Deviation from MATLAB Car.m ['r','g','c','m','y','b','w','k','r','g']:
    # 'w' (invisible on the white lanes, clashes with the unassigned
    # hall-call white) and 'k' (clashes with text and the unassigned
    # grey tint) are replaced by orange / maroon, and the duplicated
    # trailing 'r','g' by purple / olive - so every car's waiting
    # passengers stay identifiable by tint alone.

    _colors = [
        QColor("red"),
        QColor("green"),
        QColor("cyan"),
        QColor("magenta"),
        QColor("yellow"),
        QColor("blue"),
        QColor("orange"),
        QColor("maroon"),
        QColor("purple"),
        QColor("olive"),
    ]

    @classmethod
    def color(cls, car_id: int) -> QColor:
        return cls._colors[car_id - 1]

    def __init__(self, startData: Any, id: int):
        # Identifiers/state
        self.id: int = int(id)
        self.state: int = 0  # 1: up, -1: down, 0: idle
        self.floor: float = 1.0
        self.previousFloor: float = self.floor
        self.parkFloor: Any = "N/A"
        self.parkAlgorithm: int = 1

        # Time parameters
        self.doorOpeningTime: float = float(startData.doorOpeningTime)
        self.passengerTransferTime: float = float(startData.passengerTransferTime)
        self.doorClosingTime: float = float(startData.doorClosingTime)
        self.stopOverTime: float = (
            self.doorOpeningTime + self.passengerTransferTime + self.doorClosingTime
        )

        # Car parameters
        self.capacity: int = int(startData.carCapacity * startData.carCapacityFactor)
        self.velocity: float = float(startData.carVelocity)  # m/s
        self.velocityFps: float = round(self.velocity / float(startData.floorHeight), 2)  # floors/sec

        # Counters and metrics
        self.numOfServedPassengers: int = 0
        self.numOfStops: int = 0
        self.stopOverCounter: float = 0.0
        self.tripTime: float = 0.0
        self.load: int = 0

        # Lists and service data
        self.HC: HallCallLists = HallCallLists()
        self.P: PassengerLists = PassengerLists()
        self.DF: set[int] = set()

        # Categorized hall calls relative to car position
        self.HC_up_above: List[HallCall] = []
        self.HC_up_below: List[HallCall] = []
        self.HC_above: List[HallCall] = []
        self.HC_down_above: List[HallCall] = []
        self.HC_down_below: List[HallCall] = []
        self.HC_below: List[HallCall] = []

        # Ensure derived fields are consistent
        self.reset()

        # Timing parameters
        self.doorOpeningTime: float = float(startData.doorOpeningTime)
        self.passengerTransferTime: float = float(startData.passengerTransferTime)
        self.doorClosingTime: float = float(startData.doorClosingTime)
        self.stopOverTime: float = (
            self.doorOpeningTime + self.passengerTransferTime + self.doorClosingTime
        )

        # Capacity / speed
        self.capacity = int(startData.carCapacity * startData.carCapacityFactor)
        self.velocity = float(startData.carVelocity)
        # Floors per second: velocity (m/s) / floorHeight (m)
        self.velocityFps = round(self.velocity / float(startData.floorHeight), 2)

        # Dynamic state

        self.numOfServedPassengers = 0
        self.numOfStops = 0
        self.stopOverCounter = 0.0
        self.tripTime = 0.0
        self.load = 0

        # Lists
        self.HC = HallCallLists()
        self.P = PassengerLists()

        self.HC_up_above = []
        self.HC_up_below = []
        self.HC_down_above = []
        self.HC_down_below = []
        self.HC_above = []
        self.HC_below = []

        # Ensure derived fields are consistent
        self.reset()


    def reset(self) -> None:
        """
        Reset dynamic runtime state, lists, and derived caches.
        """
        self.previousFloor = self.floor
        self.state = 0

        self.stopOverCounter = 0.0
        self.numOfStops = 0
        self.doorOpeningStartTime: Optional[float] = None
        self._doorCycleFloor: Optional[float] = None
        self.tripTime = 0.0
        self.load = 0
        self.numOfServedPassengers = 0

        self.DF: set[int] = set()
        self.HC = HallCallLists()
        self.P = PassengerLists()

        # Phased alighting ([A1] in module notes):
        #   pendingAlight - passengers inside the car waiting for the
        #                   doors to open at their destination floor
        #   alighting     - lightweight dicts ({'id', 'DF'}) of passengers
        #                   walking to the landing platform during the
        #                   passenger-transfer phase (visual only; the
        #                   Passenger objects are already in 'served')
        self.pendingAlight: List[Any] = []
        self.alighting: List[dict] = []

        # Phased boarding ([A4]):
        #   pendingBoard - {'p': Passenger, 'dir': 1|2} selected at
        #                  arrival, still standing at the hall lane (and
        #                  still in the waiting lists) until doors open
        #   boarding     - {'id', 'dir'} dicts of passengers walking from
        #                  the hall lane to the cabin during the transfer
        #                  phase (visual only; already in 'travelling')
        self.pendingBoard: List[dict] = []
        self.boarding: List[dict] = []

        self.HC_up_above = []
        self.HC_up_below = []
        self.HC_down_above = []
        self.HC_down_below = []
        self.HC_above = []
        self.HC_below = []

    def checkStopOver(self, HC: HallCallLists, P: PassengerLists, currentTime: float) -> None:
        """
        Boarding/alighting handling at DF or HC floors.

        [A1] Phased stop-over. The single stopOverCounter still spans
        doorOpeningTime + passengerTransferTime + doorClosingTime, but
        alighting is no longer instantaneous:
          phase 1  counter in (close+transfer, stopOverTime]  doors opening,
                   passengers stay inside (pendingAlight)
          phase 2  counter in (close, close+transfer]         doors open:
                   passengers alight (stats recorded, moved to 'served')
                   and walk to the landing platform (self.alighting)
          phase 3  counter in [0, close]                      transfer done:
                   platform passengers disappear, doors closing
        updateDoorCycle() runs AFTER the arrival handling but BEFORE the
        counter is decremented this tick (controller.operate decrements
        afterwards), so the alight moment lands exactly at
        arrivalTime + doorOpeningTime - including doorOpeningTime == 0,
        which alights on the arrival tick like the pre-refactor code.
        """
        if (self.isAtDF() or self.isAtHC()) and (self.previousFloor != self.floor):
            # if the car is not at the same floor as before and if it is a destination of call floor -> it has stopped
            self.numOfStops += 1

        if self.isAtDF():   # if the car is at a destination floor, start the door cycle
            self.beginDropoff(currentTime)

        if self.isAtHC(): # at a call floor: answer the call, queue boarders [A4]
            self.beginPickup(HC, P, currentTime)

        self.updateDoorCycle(P, currentTime)

    def isAtDF(self) -> bool:
        return  self.floor in self.DF

    def isAtHC(self) -> bool:
        # Arrived at an assigned hall-call floor depending on current state
        up_here = any(hc.floor == self.floor for hc in self.HC.waiting[1])
        down_here = any(hc.floor == self.floor for hc in self.HC.waiting[2])
        return (
            (self.state == 1 and up_here)
            or (self.state == -1 and down_here)
            or (self.state == 0 and (up_here or down_here))
        )

    def _startDoorCycle(self, currentTime: float) -> None:
        """Record opening onset without changing the existing timer/restart policy.

        A same-floor pickup during opening/transfer belongs to the already
        available service, even though the legacy counter restarts. During
        closing (or after departure) it is a new opening event. Passengers
        already accepted keep their own original event timestamp.
        """
        if not (self.doorOpeningStartTime is not None
                and self._doorCycleFloor == self.floor
                and self.stopOverCounter > self.doorClosingTime + 1e-9):
            self.doorOpeningStartTime = float(currentTime)
            self._doorCycleFloor = self.floor
        self.stopOverCounter = float(self.stopOverTime)

    def beginDropoff(self, currentTime: float) -> None:
        """
        [A1] Arrival at a destination floor: start the door cycle. The
        passengers stay inside (pendingAlight) until the doors are open;
        the stats/list transfer moved to updateDoorCycle().
        """
        self._startDoorCycle(currentTime)
        for dir_ in (1, 2):
            if self.P.travelling[dir_]:
                passengers_here = [p for p in self.P.travelling[dir_] if p.DF == self.floor]
                for passenger in passengers_here:
                    if passenger not in self.pendingAlight:
                        self.pendingAlight.append(passenger)

        # Remove this floor from DF if present (may also be a park floor)
        self.DF.discard(self.floor)

    def updateDoorCycle(self, P: PassengerLists, currentTime: float) -> None:
        """
        [A1] Advance the phases of an ongoing stop-over. Called once per
        tick (from checkStopOver) before the counter is decremented.
        """
        eps = 1e-9
        doorsOpenAt = self.doorClosingTime + self.passengerTransferTime
        transferDoneAt = self.doorClosingTime

        # [A3] A same-floor re-pickup can restart the stop-over (pickup
        # jumps the counter back to stopOverTime - pre-existing MATLAB
        # behaviour). Without this guard, sprites already walking to the
        # platform would snap back to the doors and re-walk. The doors
        # reopening means their transfer is over: clear them.
        if self.stopOverCounter > doorsOpenAt + eps:
            if self.alighting:
                self.alighting.clear()
            if self.boarding:          # [A4] walkers count as inside now
                self.boarding.clear()

        # Phase 3 entry: transfer time has counted back to zero -> the
        # passengers moved to the landing platform disappear.
        if self.stopOverCounter <= transferDoneAt + eps:
            if self.alighting:
                self.alighting.clear()
            if self.boarding:          # [A4] boarders are inside the cabin
                self.boarding.clear()

        # Phase 2 entry: door-opening time has counted back to zero ->
        # passengers alight NOW (requirement 1). Stats are recorded here
        # (alight time = arrival + doorOpeningTime) and the lightweight
        # sprites start walking towards the landing platform.
        if self.pendingAlight and self.stopOverCounter <= doorsOpenAt + eps:
            for passenger in self.pendingAlight:
                passenger.alight(currentTime)
                P.transfer(passenger, "served")
                self.P.transfer(passenger, "served")
                self.load -= 1
                self.numOfServedPassengers += 1
                self.alighting.append({"id": passenger.id, "DF": passenger.DF})
            self.pendingAlight.clear()

        # [A4] Door-open, boarding side: the passengers selected at the
        # hall call board NOW - BT and WT_board are finalized here, while
        # primary WT uses the accepting service's opening START - and start
        # walking from the hall lane to the cabin. Runs AFTER alighting so
        # load stays <= capacity even on combined stops.
        if self.pendingBoard and self.stopOverCounter <= doorsOpenAt + eps:
            for entry in self.pendingBoard:
                passenger, dir_ = entry["p"], entry["dir"]
                P.transfer(passenger, "travelling")
                passenger.board(self.id, currentTime)
                self.P.transfer(passenger, "travelling")
                if passenger.DF not in self.DF:
                    self.DF.add(passenger.DF)
                self.load += 1
                self.boarding.append({"id": passenger.id, "dir": dir_})
            self.pendingBoard.clear()

    def alightProgress(self) -> float:
        """[A1] Walk fraction cabin -> landing platform (see _walkProgress)."""
        return self._walkProgress(self.alighting)

    def boardProgress(self) -> float:
        """[A4] Walk fraction hall lane -> cabin (see _walkProgress)."""
        return self._walkProgress(self.boarding)

    def _walkProgress(self, walkers: List[dict]) -> float:
        """
        [A1]/[A4] Fraction of a transfer-phase walk: 0.0 the moment the
        doors open, 1.0 at the far end. Because displayTraffic snapshots
        the frame BEFORE operate() decrements the counter, the visible
        ramp for a 3 s transfer (Ts=1) is 0.33 -> 0.67 -> 1.0, then the
        sprites vanish. Used by Simulator.drawCars for the animations.
        """
        if not walkers:
            return 0.0
        if self.passengerTransferTime <= 0:
            return 1.0
        doorsOpenAt = self.doorClosingTime + self.passengerTransferTime
        progress = (doorsOpenAt - self.stopOverCounter) / self.passengerTransferTime
        return min(1.0, max(0.0, progress))

    def beginPickup(self, HC: HallCallLists, P: PassengerLists, currentTime: float) -> None:
        """
        [A4] Arrival at a hall-call floor: answer the call and start the
        door cycle, but the passengers stay on the landing until the
        doors are open. Mirror of beginDropoff [A1]:
          - hall calls transfer to 'served' NOW, so HCawt is unchanged
            (the call is answered when the car arrives) and isAtHC()
            cannot retrigger;
          - the boarders are selected NOW with the original capacity
            check and leftover hall-call recreation (identical timing);
          - the selected passengers go to pendingBoard but STAY in the
            waiting lists. Primary WT freezes at this accepting service's
            opening start; WT_board keeps counting until actual boarding;
          - board()/transfers/load/DF happen in updateDoorCycle at the
            door-open moment, AFTER the alighting block, so on combined
            stops the load never exceeds capacity any more (this
            retires the [A2] transient-overload caveat).
        The stop-over counter is only (re)started when at least one
        passenger is accepted, preserving the original quirk that a
        call floor with nobody left waiting does not hold the car.
        """
        # Determine service direction at this floor
        up_here = any(hc.floor == self.floor for hc in self.HC.waiting[1])
        down_here = any(hc.floor == self.floor for hc in self.HC.waiting[2])

        if self.state == 1 or (self.state == 0 and up_here and not down_here):
            dir_ = 1
        elif self.state == -1 or (self.state == 0 and not up_here and down_here):
            dir_ = 2
        else:
            # Idle and both exist -> priority upwards (!!! needs to be checked in the future)
            dir_ = 1

        # Transfer all hall calls at this floor from waiting to served (both in car's list and global list)
        calls_here = [hc for hc in self.HC.waiting[dir_] if hc.floor == self.floor]
        for call in calls_here:
            self.HC.transfer(call)
            HC.transfer(call)

        # Waiting passengers here, minus any already queued by a stop-over
        # restart (same-floor re-pickup) in this door cycle
        pending_here = [e["p"] for e in self.pendingBoard]
        passengers_here = [p for p in self.P.waiting[dir_]
                           if p.floor == self.floor and p not in pending_here]
        # [A2] capacity credit for passengers about to alight at THIS
        # floor, debit for boarders already selected in this stop-over
        available_space = (self.capacity - self.load
                           + len(self.pendingAlight) - len(self.pendingBoard))
        if available_space < len(passengers_here):
            # Recreate a hall call for remaining passengers at this floor
            HC.add(HallCall(self.floor, currentTime, dir_))

        num_accept = max(0, min(available_space, len(passengers_here)))
        if num_accept:
            self._startDoorCycle(currentTime)
        for passenger in passengers_here[:num_accept]:
            passenger.start_pickup(self.doorOpeningStartTime)
            self.pendingBoard.append({"p": passenger, "dir": dir_})

    def updateState(self, updateType: str) -> None:
        """
        Update movement state based on current destinations and assigned calls.
        updateType: 'flexible' or 'fixed'
        #  priority upwards (!!! needs to be checked in the future)
        """
        max_dest_floor = max(self.DF, default=self.floor)
        min_dest_floor = min(self.DF, default=self.floor)

        has_dest_floor_above = max_dest_floor > self.floor
        has_dest_floor_below = min_dest_floor < self.floor

        if updateType == "flexible":
            self.state = 1 if has_dest_floor_above else -1 if has_dest_floor_below else 0
            return

        #if updateType is "fixed":
        above = self.HC_up_above + self.HC_down_above
        below = self.HC_up_below + self.HC_down_below

        has_hall_call_above = bool(above)
        has_hall_call_below = bool(below)

        # Fixed assignment: hall calls determine direction only when no DF exists.
        if self.state == 1:
            if not has_dest_floor_above and not has_hall_call_above:
                self.state = -1 if has_hall_call_below else 0
        elif self.state == -1:
            if not has_dest_floor_below and not has_hall_call_below:
                self.state = 1 if has_hall_call_above else 0
        else:    # self.state == 0
            self.updateAboveBelowHCs()
            min_hall_call_above = min((hc.floor for hc in above), default=None)
            max_hall_call_below = max((hc.floor for hc in below), default=None)

            if has_dest_floor_above:
                self.state = 1
            elif has_dest_floor_below:
                self.state = -1
            elif min_hall_call_above is not None and max_hall_call_below is not None: # !!! assigns to the closest call
                self.state = (
                    -1
                    if abs(min_hall_call_above - self.floor) > abs(max_hall_call_below - self.floor)
                    else 1
                )
            elif min_hall_call_above is not None: # max_hall_call_below is None
                self.state = 1
            elif max_hall_call_below is not None: # min_hall_call_above is None
                self.state = -1

    def updateServiceList(self, HC: HallCallLists, P: PassengerLists) -> None:
        """
        Passengers and hall calls have been assigned to the cars at first.
        Update the car's service lists with items assigned to this car id.
        """
        self.HC.waiting[1] = [hc for hc in HC.waiting[1] if hc.carId == self.id]
        self.P.waiting[1] = [p for p in P.waiting[1] if p.carId == self.id]

        self.HC.waiting[2] = [hc for hc in HC.waiting[2] if hc.carId == self.id]
        self.P.waiting[2] = [p for p in P.waiting[2] if p.carId == self.id]

    def updateAboveBelowHCs(self) -> None:
        """
        Update categorized lists of hall calls relative to the current floor.
        """
        if self.HC.waiting[1]: # up hall calls
            self.HC_up_above = [hc for hc in self.HC.waiting[1] if hc.floor >= self.floor]
            self.HC_up_below = [hc for hc in self.HC.waiting[1] if hc.floor < self.floor]
        else:
            self.HC_up_above = []
            self.HC_up_below = []

        if self.HC.waiting[2]: # down hall calls
            self.HC_down_below = [hc for hc in self.HC.waiting[2] if hc.floor <= self.floor]
            self.HC_down_above = [hc for hc in self.HC.waiting[2] if hc.floor > self.floor]
        else:
            self.HC_down_below = []
            self.HC_down_above = []

    def park(self, timeStep: float) -> Car:
        """
        Move towards a park floor if configured (parkFloor != 'N/A').
        """
        if not isinstance(self.parkFloor, str):  # Only move if park floor is set to a numeric floor
            self.floor = self.floor + _sign(float(self.parkFloor) - self.floor) * self.velocityFps * float(timeStep)
        return self

    def move(self, timeStep: float) -> None:
        """
        Move the car one step in the current state direction.
        """
        self.previousFloor = self.floor
        self.floor = self.floor + self.state * self.velocityFps * float(timeStep)
        self.tripTime = self.tripTime + float(timeStep)
