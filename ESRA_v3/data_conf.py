"""
data_conf.py
============
Python port of DataConf.m.

REC storage convention (shared by DataConf / Experiment / Simulator)
--------------------------------------------------------------------
MATLAB stored records in a 5-D cell:  RECnew{nbc, ncc, inc, int, nsc}.
The Python port uses a plain dict keyed by the SAME 1-based indices,
built with recKey():

    dataConf.RECnew[recKey(nbc, ncc, inc, int, nsc)] = Record(HC, P, cars)

Why a dict and not a NumPy 5-D array: the elements are Record objects
(object graphs of passengers/hall calls), so a NumPy array would be
dtype=object - no vectorization, no memory win, and it needs the full
shape upfront, while MATLAB's cell (and this dict) auto-grow on
assignment. NumPy stays where it earns its keep: the numeric result
tensors Pawt/HCawt in Experiment.saveResults.

Your Simulator.recordData should therefore contain the one-liner above
(see also data_structures/record.py).

Deviations from MATLAB (marked [C1]..[C5] inline):
  [C1] `startData.fileName,` was a display statement -> print().
  [C2] MATLAB's `dataConf = load(file).dataConf` REPLACES the handle
       being constructed. Python can't rebind self, so the loaded
       object's attributes are copied into self (same observable result).
  [C3] MATLAB computed nsc into a LOCAL variable; the nsc property was
       never set (the numSimulations override below it is commented
       out). We store it on self.nsc for inspection - no behaviour
       depends on it, matching MATLAB.
  [C4] MATLAB's nint/ninc labels are swapped relative to Experiment.m's
       Nicc/Nifc (TRAFFIC dim 1 vs dim 2). Only their product is used,
       so the result is identical; names kept as in DataConf.m.
  [C5] case 4 (MDP) in MATLAB calls configurationNewData with four
       output arguments (signature mismatch with case 1) and discards
       them - dead/legacy code. Ported as a loud NotImplementedError.

configurationNewData / configurationNewDataWithCustomInitials are
separate MATLAB function files not yet ported; DataConf imports them
lazily from a `configuration` module so they can be dropped in later.
"""
from __future__ import annotations

import pickle
from typing import Any, Dict, List, Tuple

from data_structures.passenger import Passenger
from data_structures.hall_call import HallCall
from simulator import Simulator

RecKey = Tuple[int, int, int, int, int]


def recKey(nbc: int, ncc: int, inc: int, int_: int, nsc: int) -> RecKey:
    """1-based key for the REC dicts, mirroring RECnew{nbc,ncc,inc,int,nsc}."""
    return (int(nbc), int(ncc), int(inc), int(int_), int(nsc))


def saveDataConf(dataConf: "DataConf", filePath: str) -> None:
    """Python counterpart of MATLAB's save(file, 'dataConf')."""
    with open(filePath, "wb") as f:
        pickle.dump(dataConf, f, protocol=pickle.HIGHEST_PROTOCOL)


def loadDataConf(filePath: str) -> "DataConf":
    """Python counterpart of MATLAB's load(file).dataConf."""
    with open(filePath, "rb") as f:
        return pickle.load(f)


class DataConf:
    """Port of the MATLAB DataConf handle class."""

    def __init__(self, startData: Any) -> None:
        # Properties (MATLAB property block)
        self.BUILDING: List[Any] = []
        self.CAR: List[List[Any]] = []
        self.TRAFFIC: List[List[Any]] = []
        self.RECnew: Dict[RecKey, Any] = {}   # initially empty
        self.RECold: Dict[RecKey, Any] = {}   # filled when loading recorded data
        self.dataType: int = int(startData.dataType)
        self.initialCars: Any = None
        self.initialP: Any = None
        self.initialHC: Any = None
        self.isInitialDispatch: Any = None
        self.nsc: Any = None

        Passenger.reset_id()
        HallCall.reset_id()

        if self.dataType == 1:          # 1: Generate new data
            configurationNewData = _importConfigFn("configurationNewData")
            configurationNewData(startData, self)

        elif self.dataType == 2:        # 2: Recorded data
            print(startData.fileName)   # [C1] MATLAB displayed the name
            loaded = loadDataConf(startData.fileName)
            # [C2] MATLAB replaced the handle with the loaded object.
            self.__dict__.update(loaded.__dict__)

            Simulator.getSetEndTime(0)

            # total = prod(size(RECnew)) in MATLAB; for the dict port the
            # number of stored records is the same quantity.
            total = len(self.RECnew)
            nbc = len(self.BUILDING)
            ncc = len(self.CAR)
            # [C4] MATLAB: nint = size(TRAFFIC,1), ninc = size(TRAFFIC,2)
            nint = len(self.TRAFFIC)
            ninc = len(self.TRAFFIC[0]) if self.TRAFFIC else 0

            self.RECold = self.RECnew
            self.RECnew = {}

            denom = nbc * ncc * nint * ninc
            nsc = round(total / denom) if denom else 0
            # [C3] MATLAB left this in a local; stored here for inspection.
            self.nsc = nsc
            # (MATLAB kept a commented-out `numSimulations = nsc` override;
            #  intentionally not applied, same as the original.)

        elif self.dataType == 3:        # 3: New data with custom initials
            configurationNewDataWithCustomInitials = _importConfigFn(
                "configurationNewDataWithCustomInitials")
            configurationNewDataWithCustomInitials(startData, self)

        elif self.dataType == 4:        # 4: MDP
            # [C5] Dead/legacy in MATLAB (outputs discarded, signature
            # mismatch). Fail loudly rather than silently misconfigure.
            raise NotImplementedError(
                "dataType=4 (MDP) is non-functional legacy code in "
                "DataConf.m; port configurationNewData's MDP path first.")

        else:
            raise ValueError(f"Unknown dataType: {self.dataType}")


def _importConfigFn(name: str):
    """Lazy import so configuration.py can be ported/dropped in later."""
    try:
        import configuration
    except ImportError as exc:
        raise ImportError(
            f"DataConf needs configuration.{name}(). Port the MATLAB "
            f"function file '{name}.m' into a module named "
            f"'configuration.py' at the project root.") from exc
    try:
        return getattr(configuration, name)
    except AttributeError as exc:
        raise ImportError(
            f"configuration.py exists but does not define {name}().") from exc
