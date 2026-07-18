from typing import Optional


class HallCall:
    """
    Python equivalent of a hall call record.

    Attributes:
        id: Sequential identifier (per-class counter).
        carId: Assigned car id, 0 when unassigned.
        floor: Floor of the hall call.
        direction: 1 for up, 2 for down,0 stopping at the floor.
        QJT: Registration time of the hall call.
        BT: Car arrival time at the hall call floor.
        WT: Waiting time (BT - QJT), defaults to 0 until boarded.
    """

    _id_counter: int = 0

    def __init__(self, floor: int, QJT: float, direction: int):
        self.id: int = self._next_id()
        self.carId: int = 0
        self.floor = floor
        self.direction: int = int(direction)
        self.QJT: float = float(QJT)     # registration time (queue join time)
        self.BT: Optional[float] = None  # boarding time
        self.WT: float = 0.0             # waiting time for the call (system response time)

    def board(self, car_id: int, current_time: float) -> None:
        """
        Assign a car to this hall call and record boarding time.

        Args:
            car_id: The id of the car that serves the call.
            current_time: The time the car arrived to serve the call.
        """
        self.carId = int(car_id)
        self.BT = float(current_time)
        self.WT = float(self.BT - self.QJT)

    @classmethod
    def reset_id(cls) -> None:
        """Reset the per-class id counter to 0."""
        cls._id_counter = 0

    @classmethod
    def _next_id(cls) -> int:
        """Get the next id for this class (and subclasses that override this)."""
        cls._id_counter += 1
        return cls._id_counter