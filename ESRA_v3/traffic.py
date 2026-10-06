"""
traffic.py
===========
Python port of Traffic.m - one (incoming %, interfloor %) traffic
combination, its route-probability matrix Pr and arrival-floor vector Pa.

Semantics (consumed by Simulator.generatePassenger):
    Pr[floor-1, DF-1]   probability that the next passenger appears on
                        `floor` wanting to travel to `DF` (sums to 1;
                        the same-floor diagonal is zero in every mode,
                        which is what simulator.py [S4] relies on)
    Pa[floor-1]         marginal arrival-floor distribution (kept for
                        the parking-algorithm-3 code that Controller.m
                        left commented out)

Deviations from MATLAB ([T1]-[T4] inline):

  [T1] destProb cases 2 and 3 never pre-allocate IntDestProb in MATLAB;
       indexed assignment auto-grows it. If the top floor happens to be
       one of the hard-coded heavy floors, the grown matrix ends up
       smaller than nf x nf and the later elementwise product errors.
       The port pre-allocates zeros((nf, nf)); numbers are identical in
       the cases that worked.

  [T2] arrivalProb cases 2/3 hard-code a 6-floor building and case 4 an
       11-floor building; destProb cases 2/3 hard-code heavy floors 5
       and [3, 4]. MATLAB would fail later with a cryptic dimension
       mismatch (or silently mis-size, see [T1]); the port validates nf
       up front and raises an informative ValueError.

  [T3] confCounter was int8 in MATLAB (overflows at 127); plain Python
       int here.

  [T4] destProbSelection / arrivalProbSelection were hard-coded locals
       (= 1) inside setRouteProbability. They are exposed as optional
       keyword arguments with default 1, so existing call sites behave
       exactly like MATLAB while tests (and future GUI options) can
       exercise the other modes.

  [T5] destProbSelection=2 never fills the heavy floor's own interfloor
       row (the cafeteria receives but emits nothing), so Pr sums to
       LESS than 1 - e.g. 0.914 for nf=8 with 60% interfloor. This is
       MATLAB's behaviour too: a random draw landing in the missing mass
       would make find() return empty and crash the Passenger
       constructor there. The port keeps the numbers identical (dead
       code today, selection is hard-coded 1) and Simulator.
       generatePassenger raises an informative error if a draw ever
       exceeds the total mass. If you enable mode 2, decide whether the
       heavy floor should emit traffic or the arrival weights should
       exclude it as an origin.

MATLAB also carried a commented-out static getSetArrivalRate; it is
intentionally not ported (the arrival rate lives in startData /
Simulator, as in the live MATLAB code path).
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

import numpy as np


class Traffic:
    """Port of the MATLAB Traffic handle class."""

    # MATLAB persistent with lazy initial value 1 (unlike the Simulator
    # statics, this one has a default when never set).
    _numInitialPassengers: int = 1

    @classmethod
    def getSetNumInitialPassengers(cls, value: Optional[int] = None) -> int:
        # Stored explicitly on the base class: a MATLAB persistent is a
        # single shared slot, so subclasses must see the same value.
        if value is not None:
            Traffic._numInitialPassengers = value
        return Traffic._numInitialPassengers

    # ------------------------------------------------------------------
    def __init__(self, inc: float, int_: float) -> None:
        self.inc = inc
        self.int = int_
        self.out = round(100 - inc - int_)
        self.Pa: Optional[np.ndarray] = None      # MATLAB: []
        self.Pr: Optional[np.ndarray] = None      # MATLAB: []
        self.confCounter: int = 0                 # [T3]

    # ------------------------------------------------------------------
    def setRouteProbability(self, building: Any,
                            destProbSelection: int = 1,
                            arrivalProbSelection: int = 1) -> None:
        """Build Pr (route matrix) and Pa (arrival vector). [T4]"""
        nf = building.nf
        self.confCounter += 1

        # DESTINATION DISTRIBUTION
        #  1 default uniform
        #  2 one floor with heavy interfloor traffic (cafeteria at breaks)
        #  3 two floors with mutual heavy traffic
        IncDestProb, IntDestProb, OutDestProb = self.destProb(
            destProbSelection, nf)

        # ARRIVAL DISTRIBUTION (MATLAB note: "DIKKAT 4 HEART CONF")
        Pa_inc, Pa_int, Pa_out = self.arrivalProb(arrivalProbSelection, nf)

        Pr_inc = (self.inc / 100) * IncDestProb * Pa_inc
        Pr_int = (self.int / 100) * IntDestProb * Pa_int
        Pr_out = (self.out / 100) * OutDestProb * Pa_out
        self.Pr = Pr_inc + Pr_int + Pr_out

        self.Pa = ((self.inc / 100) * Pa_inc[:, 0]
                   + (self.int / 100) * Pa_int[:, 0]
                   + (self.out / 100) * Pa_out[:, 0])

    # ------------------------------------------------------------------
    def destProb(self, destProbSelection: int, nf: int
                 ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Incoming: lobby (floor 1) -> uniform over floors 2..nf
        IncDestProb = np.zeros((nf, nf))
        IncDestProb[0, 1:] = 1.0 / (nf - 1)
        # Outgoing: floors 2..nf -> lobby. (MATLAB divided the zero
        # columns by nf-1 too - a no-op, not reproduced.)
        OutDestProb = np.zeros((nf, nf))
        OutDestProb[1:, 0] = 1.0

        if destProbSelection == 1:
            # 1 DEFAULT UNIFORM: floors 2..nf -> any other upper floor
            IntDestProb = np.zeros((nf, nf))
            block = 1.0 - np.eye(nf - 1)
            if nf > 2:                       # MATLAB guard (nf==2 -> zeros)
                block = block / (nf - 2)
            IntDestProb[1:, 1:] = block

        elif destProbSelection == 2:
            # 2 ONE HEAVY FLOOR (cafeteria) - hard-coded floor 5 in MATLAB.
            # NOTE [T5]: the heavy floor's own row stays zero, so the
            # combined Pr sums to < 1 (faithful to MATLAB).
            heavyFloor = [5]
            heavyProbAll = 0.4
            denom = nf - (2 + len(heavyFloor))
            if max(heavyFloor) > nf or denom < 1:
                raise ValueError(                       # [T2]
                    f"destProbSelection=2 hard-codes heavy floor "
                    f"{heavyFloor}; needs nf >= {max(heavyFloor)} and "
                    f"nf >= {3 + len(heavyFloor)}, got nf={nf}")
            IntDestProb = np.zeros((nf, nf))            # [T1]
            normalDest = [f for f in range(2, nf + 1) if f not in heavyFloor]
            nd0 = [f - 1 for f in normalDest]
            hf0 = [f - 1 for f in heavyFloor]
            IntDestProb[np.ix_(nd0, hf0)] = heavyProbAll
            for f in normalDest:
                others = [g - 1 for g in normalDest if g != f]
                IntDestProb[f - 1, others] = (1 - heavyProbAll) / denom

        elif destProbSelection == 3:
            # 3 TWO FLOORS WITH MUTUAL HEAVY TRAFFIC - hard-coded [3, 4]
            heavyFloor = [3, 4]
            heavyProb = [1.0, 1.0]
            if max(heavyFloor) > nf or nf - (1 + len(heavyFloor)) < 1:
                raise ValueError(                       # [T2]
                    f"destProbSelection=3 hard-codes heavy floors "
                    f"{heavyFloor}; needs nf >= {max(heavyFloor)}, "
                    f"got nf={nf}")
            IntDestProb = np.zeros((nf, nf))            # [T1]
            normalDest = [f for f in range(2, nf + 1) if f not in heavyFloor]
            IntDestProb[heavyFloor[0] - 1, heavyFloor[1] - 1] = heavyProb[0]
            IntDestProb[heavyFloor[1] - 1, heavyFloor[0] - 1] = heavyProb[1]
            for f in normalDest:
                # normal floors: uniform over ALL upper floors except self
                cols = [g - 1 for g in range(2, nf + 1) if g != f]
                IntDestProb[f - 1, cols] = 1.0 / (nf - 2)
            for i, f in enumerate(heavyFloor):
                cols = [g - 1 for g in normalDest if g != f]   # = normalDest
                IntDestProb[f - 1, cols] = ((1 - heavyProb[i])
                                            / (nf - (1 + len(heavyFloor))))
        else:
            raise ValueError(f"Unknown destProbSelection: {destProbSelection}")

        return IncDestProb, IntDestProb, OutDestProb

    # ------------------------------------------------------------------
    def arrivalProb(self, arrivalProbSelection: int, nf: int
                    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        def column(values: List[float]) -> np.ndarray:
            return np.tile(np.asarray(values, dtype=float)[:, None], (1, nf))

        if arrivalProbSelection == 1:
            # 1 DEFAULT UNIFORM ARRIVALS
            Painc = column([1.0] + [0.0] * (nf - 1))
            Paint = column([0.0] + [1.0 / (nf - 1)] * (nf - 1))
            Paout = column([0.0] + [1.0 / (nf - 1)] * (nf - 1))
        elif arrivalProbSelection == 2:
            if nf != 6:
                raise ValueError(                       # [T2]
                    f"arrivalProbSelection=2 hard-codes a 6-floor "
                    f"building, got nf={nf}")
            Painc = column([1, 0, 0, 0, 0, 0])
            Paint = column([0, 0, 0.5, 0.5, 0, 0])
            Paout = column([0, 1 / 3, 0, 0, 1 / 3, 1 / 3])
        elif arrivalProbSelection == 3:
            if nf != 6:
                raise ValueError(                       # [T2]
                    f"arrivalProbSelection=3 hard-codes a 6-floor "
                    f"building, got nf={nf}")
            Painc = column([1, 0, 0, 0, 0, 0])
            Paint = column([0, 0.2, 0.2, 0.2, 0.2, 0.2])
            Paout = column([0, 0.2, 0.2, 0.2, 0.2, 0.2])
        elif arrivalProbSelection == 4:
            if nf != 11:
                raise ValueError(                       # [T2]
                    f"arrivalProbSelection=4 hard-codes an 11-floor "
                    f"building, got nf={nf}")
            Painc = column([1.0] + [0.0] * 10)
            Paout = column([0.0] + [0.1] * 10)
            Paint = column([0, 0, 0, 0.2, 0.3, 0, 0, 0, 0, 0.2, 0.3])
        else:
            raise ValueError(
                f"Unknown arrivalProbSelection: {arrivalProbSelection}")

        return Painc, Paint, Paout
