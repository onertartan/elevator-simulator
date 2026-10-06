"""
tests/stubs - test-only environment setup.

Historically this module installed minimal stand-ins for the
data_structures classes so experiment.py's control flow could be tested
before the real classes were ported. The real HallCall / Passenger /
HallCallLists / PassengerLists / Record now exist and the tests run
against them directly - the stand-ins are gone.

What remains is deterministic traffic: the REAL Traffic class with Pr
overridden to an all-mass matrix (floor 2 -> destination 4) AFTER the
real route-probability math has run - so the genuine constructor/
statics/setRouteProbability code executes on every simulation, while
trip physics in the tests stay exactly predictable.
"""
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
