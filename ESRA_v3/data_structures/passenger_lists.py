from typing import Dict, List
from .hall_call_lists import HallCallLists
from .passenger import Passenger


class PassengerLists(HallCallLists):
    """
    Manages passenger lists: waiting, travelling, and served, split by direction.
    """

    def __init__(self):
        super().__init__()
        Passenger.reset_id()
        self.travelling: Dict[int, List[Passenger]] = {1: [], 2: []}
        # Ensure lists are typed for Passenger
        # self.waiting and self.served are inherited and initialized by super().__init__()

    def add(self, passenger: Passenger) -> None:
        """Plain append: passenger lists keep REGISTRATION (QJT) order.
        The floor-sorted invariant [P17] applies to hall-call lists
        only — boarding (car.beginPickup) slices P.waiting in list
        order, so reordering here would change who boards a full car."""
        self.waiting[int(passenger.direction)].append(passenger)

    def transfer(self, passenger: Passenger, transfer_to_list: str) -> None:
        """
        Move a passenger between waiting, travelling, and served lists for the given direction.
        transfer_to_list is one of: 'travelling', 'served', 'waiting'.
        """
        dir_ = int(passenger.direction)
        transfer_to_list = transfer_to_list.lower()
        if transfer_to_list == "travelling":
            self.waiting[dir_] = [p for p in self.waiting[dir_] if p.id != passenger.id]
            self.travelling[dir_].append(passenger)
        elif transfer_to_list == "served":
            self.travelling[dir_] = [p for p in self.travelling[dir_] if p.id != passenger.id]
            self.served[dir_].append(passenger)
        elif transfer_to_list == "waiting":
            self.served[dir_] = [p for p in self.served[dir_] if p.id != passenger.id]
            self.waiting[dir_].append(passenger)
        else:
            raise ValueError("transfer_to_list must be 'travelling', 'served', or 'waiting'")
