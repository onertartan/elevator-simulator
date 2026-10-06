import math
from typing import Optional
from .hall_call import HallCall

WAITING_TIME_ENDPOINT = "pickup_door_opening_start"


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
        DAT: Destination arrival time.
        TrT: Transit time (DAT - BT).
        TTD: Total time to destination (DAT - QJT).
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

    def alight(self, current_time: float) -> "Passenger":
        """
        Mark that the passenger has reached the destination.

        Args:
            current_time: The time passenger arrived to destination.

        Returns:
            self (for chaining).
        """
        self.DAT = float(current_time)
        self.TTD = float(self.DAT - self.QJT)
        self.TrT = float(self.DAT - self.BT) if self.BT is not None else None
        return self
