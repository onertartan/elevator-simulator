"""
simulator.py
============
Python port of Simulator.m - passenger generation/replay, per-simulation
recording, and the traffic-flow display.

Rendering architecture (the one structural change):
    MATLAB drew rectangles/lines/text straight into app.displayFlowUIAxes
    from the run loop. In this port the run loop lives on a worker thread
    (gui/worker.py), where touching Qt widgets is undefined behaviour.
    displayTraffic therefore keeps its MATLAB signature but builds a
    plain-data FRAME dict and emits it through the thread-safe Qt signal
    app.worker.frame; gui/flow_view.py (pyqtgraph) and
    gui/tabs/display_tab.py render it on the GUI thread. The frame layout
    is documented in _buildFrame below.

Deviations from MATLAB ([S1]-[S7] inline):

  [S1] Rendering decoupled as described above; drawCars/drawHCs/
       drawBackground/fill*Table become frame-section builders with the
       same names and the same data.
  [S2] pause(10 / 10^speed) -> time.sleep on the worker thread; same
       pacing table (speed 1 -> 1 s/frame ... 5 -> 0.1 ms/frame). If the
       speed static was never set (headless/batch use), the sleep is
       skipped instead of crashing like pause([]) would.
  [S3] mod(time, arrivalRate) == 0 -> float-safe _atPeriod (same family
       as experiment.py [D4]).
  [S4] generatePassenger inverse-CDF: MATLAB's circshift construction
       omits the `shifted(1) = 0` line (present in the commented-out
       Controller block), which silently excludes the first linear bin
       Pr(1,1) - harmless only because the same-floor diagonal of the
       route-probability matrix is zero. The port draws with an exact
       inverse-CDF (searchsorted) and unravels the linear index in
       column-major order so the (floor, DF) mapping matches MATLAB's
       find on the reshaped matrix.
  [S5] Recorded-traffic replay (checkNewPassenger case 2): the reverse
       index iteration is preserved via a reversed snapshot, and the
       passenger is copied before the transfer - mirroring MATLAB's
       copy() - so the WT stored in RECold is not mutated by the replay.
  [S6] getSetBackgroundImage is kept for API parity and still caches the
       checkerboard array; the renderer regenerates it per frame (cheap)
       rather than blitting the cached one.
  [S7] The replay match P.served QJT == time stays an exact float
       comparison: replayed time accumulates through the identical
       `time += Ts` sequence that produced the recorded QJT values, so
       the floats are bit-identical.

  [S8] Phased alighting + landing platform (see car.py [A1]/[A2]).
       drawBackground gains one right-most green column (the landing
       platform); drawCars adds per-car 'alighting' (passenger ids in
       transit to the platform) and 'alightProgress' (0..1 walk
       fraction); the frame carries landingPlatform=True so the
       renderer can detect the +1-column layout. NOTE: alight() is now
       recorded at arrival + doorOpeningTime, so trip times grow by
       doorOpeningTime versus the old instantaneous dropoff (waiting
       times Pawt/HCawt are unaffected - WT freezes at boarding).

Formatting note: MATLAB used sprintf('%d', ...) on sums that are doubles
(exact integers for Ts = 1); _fmtInt reproduces the integer look and
falls back to %g if a sum is ever fractional.
"""
from __future__ import annotations

import copy
import math
import time as _time
from typing import Any, Dict, List, Optional

import numpy as np

from data_structures.passenger import Passenger
from data_structures.hall_call import HallCall
from data_structures.record import Record


def _atPeriod(t: float, period: float, eps: float = 1e-9) -> bool:
    """[S3] Float-safe mod(t, period) == 0 (see experiment.py [D4])."""
    if period == 0 or math.isinf(period):
        return t == 0
    r = math.fmod(t, period)
    return abs(r) < eps or abs(r - period) < eps


def _fmtInt(x: float) -> str:
    """sprintf('%d', x) for sums that are integer-valued doubles."""
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return str(x)
    if math.isnan(xf):
        return "NaN"
    return str(int(xf)) if xf.is_integer() else f"{xf:g}"


def _fmtMean(values: List[float]) -> str:
    """sprintf('%.2f', mean(v)); MATLAB mean([]) is NaN."""
    if not values:
        return "NaN"
    return f"{float(np.mean(values)):.2f}"


class Simulator:
    """Port of the MATLAB Simulator handle class."""

    # ------------------------------------------------------------------
    # Static setget methods (MATLAB persistent variables)
    # ------------------------------------------------------------------
    _speed: Optional[float] = None
    _backgroundImage: Optional[np.ndarray] = None
    _displayTrafficFlow: Optional[bool] = None
    _displayTabularData: Optional[bool] = None
    _endTime: Optional[float] = None

    @classmethod
    def setgetSpeed(cls, speed: Optional[float] = None) -> Optional[float]:
        if speed is not None:
            cls._speed = speed
        return cls._speed

    @classmethod
    def getSetBackgroundImage(cls, image: Optional[np.ndarray] = None
                              ) -> Optional[np.ndarray]:
        if image is not None:
            cls._backgroundImage = image
        return cls._backgroundImage

    @classmethod
    def getSetDisplayTrafficFlow(cls, value: Optional[bool] = None
                                 ) -> Optional[bool]:
        if value is not None:
            cls._displayTrafficFlow = value
        return cls._displayTrafficFlow

    @classmethod
    def getSetDisplayTabularData(cls, value: Optional[bool] = None
                                 ) -> Optional[bool]:
        if value is not None:
            cls._displayTabularData = value
        return cls._displayTabularData

    @classmethod
    def getSetEndTime(cls, endTime: Optional[float] = None
                      ) -> Optional[float]:
        if endTime is not None:
            cls._endTime = endTime
        return cls._endTime

    @staticmethod
    def clearScreen(app: Any) -> None:
        """
        Port of the MATLAB clearScreen (cla + background). Must be called
        from the GUI thread (MATLAB called it from checkbox/terminate
        callbacks, which are GUI-side in the port too).
        """
        view = Simulator._flowView(app)
        if view is not None:
            view.clear_view()

    # ------------------------------------------------------------------
    def __init__(self, startData: Any, numMaxConfs: Any) -> None:
        self.dataType = startData.dataType

        self.time: float = 0
        self.refTime = startData.refTime      # removes initial transient
        self.endTime = startData.endTime
        self.arrivalRate = startData.arrivalRate
        self.decisionPeriod = startData.decisionPeriod
        self.Ts: float = 1

        self.numSimulations = startData.numSimulations
        self.numMaxSimulations = (numMaxConfs.Nbc * numMaxConfs.Ncc
                                  * numMaxConfs.Nicc * numMaxConfs.Nifc
                                  * self.numSimulations)
        self.confIndices: Any = None
        self.numMaxConfs = numMaxConfs
        self.totalRunCounter: int = 0
        self.totalRunTime: float = 0
        self.lastRunTime: float = 0

    # ------------------------------------------------------------------
    # Passenger generation / replay
    # ------------------------------------------------------------------
    def checkNewPassenger(self, HC: Any, P: Any, traffic: Any) -> None:
        # 1: New traffic  2: Recorded traffic  3: New traffic w/ initials
        if self.dataType == 1:
            if (_atPeriod(self.time, self.arrivalRate)
                    and self.time < Simulator.getSetEndTime()
                    and self.time > 0):
                self.generatePassenger(HC, P, traffic)

        elif self.dataType == 2:
            for dir_ in (1, 2):
                # [S5] snapshot + reversed = MATLAB's length:-1:1 loop
                matches = [p for p in P.served[dir_]
                           if p.QJT == self.time]          # [S7]
                for passenger in reversed(matches):
                    # copy so the WT recorded in RECold isn't mutated
                    P.transfer(copy.copy(passenger), "waiting")
                    if not any(hc.floor == passenger.floor
                               for hc in HC.waiting[dir_]):
                        HC.add(HallCall(passenger.floor, self.time, dir_))

        elif self.dataType == 3:
            if (self.arrivalRate != 0
                    and _atPeriod(self.time, self.arrivalRate)
                    and self.time < self.endTime   # instance, not static
                    and self.time > 0):
                self.generatePassenger(HC, P, traffic)

    def generatePassenger(self, HC: Any, P: Any, traffic: Any) -> None:
        """[S4] Draw (floor, DF) from the route-probability matrix."""
        Pr = np.asarray(traffic.Pr, dtype=float)
        cumPr = np.cumsum(Pr.flatten(order="F"))   # column-major like Pr(:)
        r = np.random.rand()
        linearIndex = int(np.searchsorted(cumPr, r, side="left"))
        if linearIndex >= cumPr.size:
            # Only reachable when the route matrix's mass is < 1
            # (see traffic.py [T5], destProbSelection=2).
            raise ValueError(
                f"random draw {r:.4f} exceeds total route-probability "
                f"mass {cumPr[-1]:.4f}; Pr does not sum to 1 "
                f"(traffic.py [T5])")
        floor0, DF0 = np.unravel_index(linearIndex, Pr.shape, order="F")
        floor, DF = int(floor0) + 1, int(DF0) + 1

        passenger = Passenger(floor, self.time, DF)
        dir_ = passenger.direction
        P.add(passenger)
        # if there is no HC at the passenger floor, generate a new HC
        if not any(hc.floor == passenger.floor for hc in HC.waiting[dir_]):
            HC.add(HallCall(floor, self.time, dir_))

    # ------------------------------------------------------------------
    def recordData(self, HC: Any, P: Any, cars: List[Any],
                   dataConf: Any, indices: Any) -> None:
        # MATLAB sorts served passengers by QJT (stable) before recording
        from data_conf import recKey   # local: avoids circular import
        P.served[1] = sorted(P.served[1], key=lambda p: p.QJT)
        P.served[2] = sorted(P.served[2], key=lambda p: p.QJT)
        dataConf.RECnew[recKey(indices.nbc, indices.ncc, indices.inc,
                               indices.int, indices.nsc)] = Record(HC, P, cars)

    # ------------------------------------------------------------------
    # Display (frame-based; see module docstring) [S1]
    # ------------------------------------------------------------------
    def displayTraffic(self, building: Any, traffic: Any, cars: List[Any],
                       HC: Any, P: Any, app: Any, nsc: int) -> None:
        frame: Dict[str, Any] = {
            "time": self.time,
            "nf": building.nf,
            "numCars": len(cars),
            "traffic": {"inc": traffic.inc, "int": traffic.int,
                        "out": traffic.out},
            "landingPlatform": True,   # [S8] frame layout has +1 column
            "flow": None,
            "tables": None,
            "counters": self.fillCountersTable(),
        }
        if Simulator.getSetDisplayTrafficFlow():
            self.drawBackground(building.nf, len(cars))    # caches [S6]
            frame["flow"] = {
                "cars": self.drawCars(cars),
                "hallCalls": self.drawHCs(P, HC),
            }
        if Simulator.getSetDisplayTabularData():
            frame["tables"] = {
                "car": self.fillCarTable(cars),
                "passengers": self.fillPassengerTables(P),
                "results": self.fillResultsTable(HC, P, cars),
            }

        self._emitFrame(app, frame)

        # [S2] MATLAB: pause(10 / 10^speed)
        speed = Simulator.setgetSpeed()
        if speed is not None:
            _time.sleep(10 / (10 ** speed))

    # ---- frame-section builders (names kept from MATLAB) -------------
    def drawBackground(self, nf: int, numCars: int) -> np.ndarray:
        """
        Checkerboard for the Up/Down columns + white car columns [S6].
        [S8] One extra right-most column: the LANDING PLATFORM, where
        alighting passengers walk to (green-tinted checkerboard).
        Layout: col 0 Up | col 1 Down | cols 2..numCars+1 cars |
                col numCars+2 landing platform.
        """
        b = np.ones((nf, 2 + numCars + 1, 3))
        b[0::2, 0, :] = 0.85
        b[1::2, 0, :] = 0.70
        b[0::2, 1, :] = 0.70
        b[1::2, 1, :] = 0.85
        # landing platform (right-most column)
        b[0::2, -1] = (0.88, 0.95, 0.88)
        b[1::2, -1] = (0.78, 0.90, 0.78)
        Simulator.getSetBackgroundImage(b)
        return b

    def drawCars(self, cars: List[Any]) -> List[Dict[str, Any]]:
        # [S8] alighting/alightProgress drive the walk-to-landing-platform
        # animation: ids of passengers currently between the car doors and
        # the platform, plus the shared 0..1 walk fraction for this tick.
        # [S9] 'alight' is the {DF: passenger count} map the sprite
        # renderer's destination-circle badges expect (flow_view [N1]);
        # it counts passengers still riding inside the car.
        out = []
        for car in cars:
            alight: Dict[Any, int] = {}
            for dir_ in (1, 2):
                for p in car.P.travelling[dir_]:
                    alight[p.DF] = alight.get(p.DF, 0) + 1
            out.append({
                "id": car.id,
                "floor": float(car.floor),
                "state": int(car.state),
                "stopOverCounter": float(car.stopOverCounter),
                "load": int(car.load),
                "DF": sorted(car.DF),
                "alight": alight,
                "alighting": [a["id"] for a in car.alighting],
                "alightProgress": car.alightProgress(),
            })
        return out

    def drawHCs(self, P: Any, HC: Any) -> Dict[int, List[Dict[str, Any]]]:
        out: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
        for dir_ in (1, 2):
            for hc in HC.waiting[dir_]:
                out[dir_].append({
                    "floor": hc.floor,
                    "carId": int(hc.carId),
                    "waitingCount": sum(
                        1 for p in P.waiting[dir_] if p.floor == hc.floor),
                })
        return out

    def fillCarTable(self, cars: List[Any]) -> Dict[str, Any]:
        columns = [f"Car-{i}" for i in range(1, len(cars) + 1)]
        rows = ["Car position", "Car State", "Stopover counter", "Car load",
                "Pickup floors", "Car trip time",
                "Number of served passengers"]
        data = [
            [f"{car.floor:.1f}" for car in cars],
            [str(car.state) for car in cars],
            [_fmtInt(car.stopOverCounter) for car in cars],
            [str(car.load) for car in cars],
            [", ".join(str(hc.floor)
                       for hc in (list(car.HC.waiting[1])
                                  + list(car.HC.waiting[2])))
             for car in cars],
            [_fmtInt(car.tripTime) for car in cars],
            [str(car.numOfServedPassengers) for car in cars],
        ]
        return {"columns": columns, "rows": rows, "data": data}

    def fillPassengerTables(self, P: Any) -> Dict[int, Dict[str, Any]]:
        tables: Dict[int, Dict[str, Any]] = {}
        rows = ["Call Floor", "Destination Floor", "Queue join time",
                "Waiting time", "Car id"]
        for dir_ in (1, 2):
            waiting = P.waiting[dir_]
            if waiting:
                tables[dir_] = {
                    "columns": [f"id-{p.id}" for p in waiting],
                    "rows": rows,
                    "data": [
                        [str(p.floor) for p in waiting],
                        [str(p.DF) for p in waiting],
                        [_fmtInt(p.QJT) for p in waiting],
                        [_fmtInt(p.WT) for p in waiting],
                        [str(p.carId) for p in waiting],
                    ],
                }
            else:
                tables[dir_] = {"columns": [], "rows": [], "data": []}
        return tables

    def fillCountersTable(self) -> List[str]:
        idx = self.confIndices
        maxIdx = self.numMaxConfs
        totalSeconds = round(self.totalRunTime)
        hours, rem = divmod(totalSeconds, 3600)
        minutes, seconds = divmod(rem, 60)
        timeStr = f"{hours}:{minutes:02d}:{seconds:02d}"
        if idx is None or maxIdx is None:
            return ["-", "-", "-", "-", "-", timeStr]
        return [
            f"{idx.nbc}/{maxIdx.Nbc}",
            f"{idx.ncc}/{maxIdx.Ncc}",
            # quirky product kept from MATLAB:
            f"{idx.inc * idx.int}/{maxIdx.Nicc * maxIdx.Nifc}",
            f"{idx.nsc}/{self.numSimulations}",
            f"{self.totalRunCounter}/{self.numMaxSimulations}",
            timeStr,
        ]

    def fillResultsTable(self, HC: Any, P: Any,
                         cars: List[Any]) -> List[str]:
        tripTimes = [car.tripTime for car in cars]
        if self.dataType == 3:
            p_wt = [p.WT for p in list(P.served[1]) + list(P.served[2])
                    if p.QJT != -1]
            hc_wt = [h.WT for h in list(HC.served[1]) + list(HC.served[2])
                     if h.QJT != -1]
            return [
                _fmtInt(sum(tripTimes)),          # Total car trip time
                _fmtInt(sum(p_wt)),               # Total passenger waiting
                _fmtInt(sum(hc_wt)),              # Total hall call waiting
                str(len(p_wt)),                   # Served passengers
                str(len(hc_wt)),                  # Responded hall calls
                _fmtMean(tripTimes),              # Avg car trip time
                _fmtMean(p_wt),                   # Avg passenger waiting
                _fmtMean(hc_wt),                  # Avg hall call waiting
            ]
        p_wt = [p.WT for p in list(P.served[1]) + list(P.served[2])]
        hc_wt = [h.WT for h in list(HC.served[1]) + list(HC.served[2])]
        return [
            _fmtInt(sum(tripTimes)),
            _fmtInt(sum(p_wt)),
            _fmtInt(sum(hc_wt)),
            str(sum(car.numOfServedPassengers for car in cars)),
            str(len(HC.served[1]) + len(HC.served[2])),
            _fmtMean(tripTimes),
            _fmtMean(p_wt),
            _fmtMean(hc_wt),
        ]

    # ---- delivery -----------------------------------------------------
    @staticmethod
    def _emitFrame(app: Any, frame: Dict[str, Any]) -> None:
        """Hand the frame to the GUI thread via the worker's Qt signal."""
        worker = getattr(app, "worker", None) if app is not None else None
        if worker is not None and hasattr(worker, "frame"):
            worker.frame.emit(frame)

    @staticmethod
    def _flowView(app: Any):
        displayTab = getattr(app, "display_tab", None) if app else None
        return getattr(displayTab, "flow_view", None) if displayTab else None