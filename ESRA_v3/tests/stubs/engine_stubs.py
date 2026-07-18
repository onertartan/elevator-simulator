"""
tests/stubs - minimal stand-ins for the engine classes, ONLY for testing
experiment.py's control flow. Your real converted classes replace these.
The stub Simulator advances time and serves one passenger via the stub
Controller, so the while-loop actually iterates a few times.
"""
import math
import sys
import types
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# data_structures stubs
# ---------------------------------------------------------------------------
ds = types.ModuleType("data_structures")
sys.modules["data_structures"] = ds


def _submodule(name, **attrs):
    mod = types.ModuleType(f"data_structures.{name}")
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[f"data_structures.{name}"] = mod
    setattr(ds, name, mod)
    return mod


class HallCall:
    """Functional test stub mirroring HallCall.m."""
    _next_id = 1

    @classmethod
    def resetId(cls):
        cls._next_id = 1

    def __init__(self, floor, QJT, direction):
        self.id = HallCall._next_id
        HallCall._next_id += 1
        self.carId = 0
        self.floor = floor
        self.direction = direction
        self.QJT = QJT
        self.BT = None
        self.WT = 0.0

    def board(self, carId, currentTime):
        self.carId = carId
        self.BT = currentTime
        self.WT = self.BT - self.QJT


class Passenger(HallCall):
    """Functional test stub mirroring Passenger.m."""
    _next_id = 1

    @classmethod
    def resetId(cls):
        cls._next_id = 1

    def __init__(self, floor, QJT, DF):
        direction = 1 if DF > floor else 2   # ceil(|sign(DF-floor)-.5|)
        super().__init__(floor, QJT, direction)
        self.id = Passenger._next_id         # Passenger has its own counter
        Passenger._next_id += 1
        self.DF = DF
        self.DAT = None
        self.TrT = None
        self.TTD = None

    def alight(self, currentTime):
        self.DAT = currentTime
        self.TTD = self.DAT - self.QJT
        self.TrT = self.DAT - self.BT


class HallCallLists:
    """Functional test stub mirroring HallCallLists.m."""

    def __init__(self):
        self.waiting = {1: [], 2: []}
        self.served = {1: [], 2: []}

    def add(self, hallCall):
        self.waiting[hallCall.direction].append(hallCall)

    def transfer(self, hallCall):
        d = hallCall.direction
        self.served[d].append(hallCall)
        self.waiting[d] = [h for h in self.waiting[d] if h.id != hallCall.id]

    def clearCarIds(self):
        for d in (1, 2):
            for h in self.waiting[d]:
                h.carId = 0


class PassengerLists(HallCallLists):
    """Functional test stub mirroring PassengerLists.m."""

    def __init__(self):
        super().__init__()
        self.travelling = {1: [], 2: []}

    def transfer(self, passenger, transferToList):
        d = passenger.direction
        if transferToList == "travelling":
            self.waiting[d] = [p for p in self.waiting[d]
                               if p.id != passenger.id]
            self.travelling[d].append(passenger)
        elif transferToList == "served":
            self.travelling[d] = [p for p in self.travelling[d]
                                  if p.id != passenger.id]
            self.served[d].append(passenger)
        elif transferToList == "waiting":
            self.served[d] = [p for p in self.served[d]
                              if p.id != passenger.id]
            self.waiting[d].append(passenger)


class Record:
    """Mirror of data_structures/record.py (the stub package shadows it)."""

    def __init__(self, HC, P, cars):
        self.HC = HC
        self.P = P
        self.cars = cars


_submodule("record", Record=Record)
_submodule("passenger", Passenger=Passenger)
_submodule("hall_call", HallCall=HallCall)
_submodule("hall_call_lists", HallCallLists=HallCallLists)
_submodule("passenger_lists", PassengerLists=PassengerLists)







# ---------------------------------------------------------------------------
# NOTE: only the data_structures classes remain stubbed (functional
# mirrors of the .m sources) - tests exercise the REAL configuration,
# car, building, controller, simulator, traffic and dispatchers.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Traffic for tests: the REAL Traffic class, with Pr overridden to a
# deterministic all-mass matrix (floor 2 -> destination 4) AFTER the real
# route-probability math has run - so the genuine constructor/statics/
# setRouteProbability code executes on every simulation, while trip
# physics in the tests stay exactly predictable.
# ---------------------------------------------------------------------------
import numpy as _np
from traffic import Traffic as _RealTraffic


class TestTraffic(_RealTraffic):
    def setRouteProbability(self, building, *args, **kwargs):
        super().setRouteProbability(building, *args, **kwargs)   # real math
        nf = building.nf
        self.Pr = _np.zeros((nf, nf))
        if nf >= 4:
            self.Pr[1, 3] = 1.0          # (floor 2, DF 4), 0-based
        else:
            self.Pr[0, nf - 1] = 1.0


# configuration.generateTrafficConf must build TestTraffic instances
import configuration as _configuration
_configuration.Traffic = TestTraffic
