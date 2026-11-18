import math
from typing import Optional
from .hall_call import HallCall

WAITING_TIME_ENDPOINT = "pickup_door_opening_start"
TRANSIT_TIME_ENDPOINT = "destination_door_opening_start"   # [A7]


class Passenger(HallCall):
    """
    Passenger extends HallCall with destination and timing details.

    Attributes:
        doorOpeningStartTime: Opening start of the pickup service that accepts
            this passenger; None until a place in the car is reserved.
        WT: Queue join until that opening starts; zero when the passenger
            arrives during the accepting service's opening/open phase.
        WT_board: Queue join until boarding (BT - QJT), the animation-aligned
            secondary measure. BT remains the fully-open/transfer-start event.
        DF: Destination floor.
        DAT: Destination arrival time: opening START of the drop-off door
            cycle at the destination floor (ISO 8100-32, 3.33) [A7].
        TrT: Transit time (ISO 8100-32, 3.35): pickup opening start (or the
            queue join, if the passenger arrived during opening) until DAT.
        TTD: Time to destination (DAT - QJT) = WT + TrT exactly [A7].
            Before [A7] DAT/TrT were taken at fully-open doors and
            TTD = WT_board + TrT; the durations of TrT are unchanged, only
            their endpoints moved by the destination door-opening time.
    """

    _id_counter: int = 0  # independent counter from HallCall

    def __init__(self, floor: int, QJT: float, DF: int):
        # Direction calculation matches the MATLAB logic:
        # 1 when DF >= floor, 2 when DF < floor.
        direction = 1 if DF >= floor else 2
        super().__init__(floor, QJT, direction)
        self.DF: int = int(DF)
        self.reset_service_timing()

    def reset_service_timing(self) -> None:
        """Clear one journey's outcome, also when replaying a recorded passenger.

        Keep identity, origin, destination and queue-join time; never carry a
        previous run's pickup timestamp into a new dispatch/boarding service.
        """
        self.carId = 0
        self.BT = None
        self.WT = 0.0
        self.WT_board = 0.0
        self.doorOpeningStartTime: Optional[float] = None
        self.DAT: Optional[float] = None
        self.TrT: Optional[float] = None
        self.TTD: Optional[float] = None

    def start_pickup(self, door_opening_start_time: float) -> None:
        """Freeze primary waiting ONLY after capacity-based pickup acceptance."""
        start = float(door_opening_start_time)
        if not math.isfinite(start):
            raise ValueError("pickup door-opening start must be finite")
        self.doorOpeningStartTime = start
        # This overlap rule is not subtraction/clipping of an estimated wait:
        # someone joining an already opening/open accepting service waits zero.
        self.WT = max(self.QJT, start) - self.QJT

    def advance_waiting_time(self, current_time: float) -> None:
        """Update the live queue display without advancing a frozen primary WT."""
        self.WT_board = float(current_time - self.QJT)
        if self.doorOpeningStartTime is None:
            self.WT = self.WT_board

    def board(self, car_id: int, current_time: float) -> None:
        """Board at fully-open doors; preserve BT/TrT and the earlier WT endpoint.

        Direct two-argument calls without start_pickup represent instantaneous
        service (also used for the QJT=BT=-1 custom-initial cabin passengers).
        The simulation always records start_pickup before calling this method.
        """
        if self.doorOpeningStartTime is None:
            self.start_pickup(current_time)
        if (not math.isfinite(current_time) or current_time < self.QJT
                or current_time < self.doorOpeningStartTime):
            raise ValueError("boarding must not precede queue join or pickup opening")
        super().board(car_id, current_time)
        self.WT_board = self.BT - self.QJT
        self.WT = max(self.QJT, self.doorOpeningStartTime) - self.QJT

    @classmethod
    def reset_id(cls) -> None:
        """Reset Passenger-specific counter to 0."""
        cls._id_counter = 0

    @classmethod
    def _next_id(cls) -> int:
        """Passengers have their own id space, separate from HallCall."""
        cls._id_counter += 1
        return cls._id_counter

    def alight(self, current_time: float,
               destination_opening_start: Optional[float] = None) -> "Passenger":
        """
        Mark that the passenger has reached the destination. [A7] ISO 8100-32
        endpoints: DAT is the instant the car's doors BEGIN to open at the
        destination floor (3.33 time to destination), TrT runs from the
        pickup opening start - or the queue join, if later (3.35 NOTE) - to
        that instant, so TTD = DAT - QJT = WT + TrT holds exactly.

        Args:
            current_time: Tick at which the engine processes the alighting
                (doors fully open); kept as the fallback when the car gave
                no opening-start timestamp (instantaneous service, cabin
                passengers loaded from an initials file).
            destination_opening_start: Opening start of the drop-off door
                cycle at the destination floor (Car.doorOpeningStartTime).

        Returns:
            self (for chaining).
        """
        arrival = (float(destination_opening_start)
                   if destination_opening_start is not None else float(current_time))
        if not math.isfinite(arrival):
            raise ValueError("destination arrival time must be finite")
        self.DAT = arrival
        self.TTD = float(self.DAT - self.QJT)
        if self.doorOpeningStartTime is not None:
            self.TrT = float(self.DAT - max(self.QJT, self.doorOpeningStartTime))
        elif self.BT is not None:
            self.TrT = float(self.DAT - self.BT)
        else:
            self.TrT = None
        return self
