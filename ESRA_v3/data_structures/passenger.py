from typing import Optional
from .hall_call import HallCall


class Passenger(HallCall):
    """
    Passenger extends HallCall with destination and timing details.

    Attributes:
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
        self.DAT: Optional[float] = None
        self.TrT: Optional[float] = None
        self.TTD: Optional[float] = None

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
