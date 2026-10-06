"""
tests/check_real_data_structures.py
====================================
Run this ON YOUR MACHINE (no stubs) to verify that YOUR converted
data_structures package exposes everything the engine calls:

    python tests/check_real_data_structures.py

The sandbox test suite substitutes functional stubs for these classes,
so a green smoke suite does not prove your real package is compatible -
this script does.
"""
import os
import sys
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists
from data_structures.record import Record
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


# --- HallCall ------------------------------------------------------------
HallCall.reset_id()
hc = HallCall(3, 0.0, 1)
check(hasattr(hc, "id") and hasattr(hc, "carId"), "HallCall.id/carId")
check(hc.WT == 0, "HallCall.WT starts at 0")
check(hasattr(hc, "QJT") and hc.QJT == 0.0, "HallCall.QJT")

# --- Passenger -------------------------------------------------------------
Passenger.reset_id()
p_up = Passenger(2, 0.0, 5)
p_down = Passenger(5, 0.0, 2)
check(p_up.direction == 1 and p_down.direction == 2,
      "Passenger.direction from (floor, DF)")
p_up.board(1, 4.0)
check(p_up.BT == 4.0 and p_up.WT == 4.0, "Passenger.board sets BT/WT")
p_up.alight(9.0)
check(p_up.DAT == 9.0 and p_up.TTD == 9.0 and p_up.TrT == 5.0,
      "Passenger.alight sets DAT/TTD/TrT")

# --- HallCallLists ---------------------------------------------------------
HCL = HallCallLists()
check(1 in HCL.waiting and 2 in HCL.waiting, "waiting keyed by 1/2")
HCL.add(hc)
check(hc in HCL.waiting[1], "HallCallLists.add by direction")
HCL.transfer(hc)
check(hc in HCL.served[1] and hc not in HCL.waiting[1],
      "HallCallLists.transfer waiting -> served")
check(hasattr(HCL, "clearCarIds"), "HallCallLists.clearCarIds exists")

# --- PassengerLists ----------------------------------------------------------
PL = PassengerLists()
check(hasattr(PL, "travelling"), "PassengerLists.travelling")
PL.add(p_down)                      # inherited add used by generatePassenger
check(p_down in PL.waiting[2], "PassengerLists.add (inherited)")
PL.transfer(p_down, "travelling")
check(p_down in PL.travelling[2] and p_down not in PL.waiting[2],
      "transfer waiting -> travelling")
PL.transfer(p_down, "served")
check(p_down in PL.served[2], "transfer travelling -> served")
PL.transfer(p_down, "waiting")
check(p_down in PL.waiting[2] and p_down not in PL.served[2],
      "transfer served -> waiting (recorded replay)")

# --- Record ---------------------------------------------------------------
r = Record(HCL, PL, [])
check(r.HC is HCL and r.P is PL, "Record stores HC/P/cars")

# --- deepcopy (resetVariables / replay rely on it) --------------------------
import copy
check(copy.deepcopy(PL) is not PL, "PassengerLists deep-copyable")

if failures:
    print("INCOMPATIBILITIES FOUND:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("Your data_structures package is compatible with the engine. OK")
