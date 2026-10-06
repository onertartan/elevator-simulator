import bisect
from typing import Dict, List
from .hall_call import HallCall


class HallCallLists:
    """
    Manages up/down hall call lists for waiting and served.
    Direction keys: 1 (up/same), 2 (down).

    [P17] waiting lists are kept FLOOR-SORTED at insertion (see add).
    The metaheuristic dispatchers align chromosome genes positionally
    with these lists (decision/meta/metaheuristic_dispatcher.py [P17]);
    transfer() preserves order, so the invariant holds everywhere.
    """

    def __init__(self):
        self.waiting: Dict[int, List[HallCall]] = {1: [], 2: []}
        self.served: Dict[int, List[HallCall]] = {1: [], 2: []}

    def add(self, hall_call: HallCall) -> None:
        """Insert hall_call into its direction's waiting list, keeping
        the list sorted by floor ([P17]; insort-right keeps registration
        order among equal floors, matching MATLAB's stable sort)."""
        dir_ = int(hall_call.direction)
        bisect.insort(self.waiting[dir_], hall_call,
                      key=lambda hc: hc.floor)

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