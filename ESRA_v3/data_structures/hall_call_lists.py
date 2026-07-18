from typing import Dict, List
from .hall_call import HallCall


class HallCallLists:
    """
    Manages up/down hall call lists for waiting and served.
    Direction keys: 1 (up/same), 2 (down).
    """

    def __init__(self):
        self.waiting: Dict[int, List[HallCall]] = {1: [], 2: []}
        self.served: Dict[int, List[HallCall]] = {1: [], 2: []}

    def add(self, hall_call: HallCall) -> None:
        """Add hall_call to the corresponding waiting list by direction."""
        dir_ = int(hall_call.direction)
        self.waiting[dir_].append(hall_call)

    def transfer(self, hall_call: HallCall) -> None:
        """
        Move hall_call from waiting to served lists within the same direction.
        Matching by unique id.
        """
        dir_ = int(hall_call.direction)
        self.waiting[dir_] = [hc for hc in self.waiting[dir_] if hc.id != hall_call.id]
        self.served[dir_].append(hall_call)

    def clear_car_ids(self) -> None:
        """Clear car assignments of all hall calls in waiting lists."""
        for dir_ in (1, 2):
            for hc in self.waiting[dir_]:
                hc.carId = 0