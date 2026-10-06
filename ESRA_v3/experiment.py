"""
experiment.py
=============
Python port of Experiment.m - the main experiment driver that sweeps
building / car / traffic configurations and runs the simulation loop.

Deviations from the MATLAB original (each marked inline as [D1]..[D6]):

  [D1] pauseCheck no longer busy-waits. MATLAB needed
       `while pauseFlag; pause(0.001); end` because MATLAB is single-
       threaded and pause() is what lets button callbacks execute. Here
       the experiment runs in a worker thread (see gui/worker.py), so
       pauseCheck blocks on a threading.Event: zero CPU, instant wake-up,
       and Terminate can interrupt a paused run. The method name and its
       call site in the loop are unchanged.

  [D2] drawnow is gone. Off the GUI thread there is nothing to pump;
       UI refresh must happen via Qt signals emitted from displayTraffic
       (see the thread-safety note in gui/worker.py).

  [D3] assignin('base', ...) has no Python equivalent. Results are kept
       on the instance instead: self.dataConf, self.Pawt, self.HCawt,
       self.resultsFile - and run() returns dataConf.

  [D4] mod(t, T) == 0 is replaced by a float-safe _atPeriod() check,
       since simulator.time accumulates floating-point steps.

  [D5] The widget clean-up MATLAB did inside terminationCheck
       (cla(app.displayFlowUIAxes), Visible='off') must run on the GUI
       thread in Qt, so it lives in the GUI's Terminate slot now;
       terminationCheck here only decides whether to stop.

  [D6] In MATLAB, `cars(1).floor = 1; randi(building.nf);` - the randi
       call after the semicolon is dead code. The port keeps the
       intentional part (floor = 1, per the inline comment "set to 1 to
       prove we obtain the same results").

  [D7] REC storage: RECnew{nbc,ncc,inc,int,nsc} (MATLAB 5-D cell) is a
       dict keyed by the same 1-based indices via data_conf.recKey().
       A NumPy object array was considered and rejected: the payloads
       are Record object graphs, so dtype=object gives no vectorization
       and would need a preallocated dense shape, while the dict
       auto-grows on assignment exactly like the cell did. NumPy stays
       for the numeric Pawt/HCawt tensors in saveResults.
       Simulator.recordData must write:
         dataConf.RECnew[recKey(i.nbc,i.ncc,i.inc,i.int,i.nsc)] = Record(HC,P,cars)

  [D8] saveResults is sparse-grid-safe. The traffic grid legitimately
       contains empty cells (inc + int > 100, see generateTrafficConf),
       and for range sweeps MATLAB's saveResults had three latent bugs:
       (a) it dereferenced TRAFFIC{end,end}.inc, which errors when that
       corner combo is invalid; (b) it built row/column names with step
       1 (incomingMin:incomingMax) while the tables have step-10
       dimensions, so array2table would error; (c) it indexed RECnew
       cells that were never written for invalid combos. The port
       derives labels from the fixed step-10 sweep and records missing
       combos as NaN. Single-value traffic (the GUI's fixed sliders)
       behaves byte-identically to MATLAB.

Imports below assume the module layout used so far (data_structures
package, one module per class). Adjust the paths if your layout differs.
"""
from __future__ import annotations

import copy
import math
import os
import threading
import time
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

import numpy as np

# --- Engine imports: adjust to your actual module layout -------------------
from controller import Controller
from data_conf import DataConf, recKey
from configuration import TRAFFIC_STEP
from simulator import Simulator
from traffic import Traffic
from data_structures.passenger import Passenger
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger_lists import PassengerLists


def _atPeriod(t: float, period: float, eps: float = 1e-9) -> bool:
    """
    [D4] Float-safe port of MATLAB `mod(t, period) == 0`.

    MATLAB edge cases preserved:
      mod(t, Inf) == t  -> true only at t == 0
      mod(t, 0)   == t  -> true only at t == 0
    """
    if period == 0 or math.isinf(period):
        return t == 0
    r = math.fmod(t, period)
    return abs(r) < eps or abs(r - period) < eps


class Experiment:
    """Port of the MATLAB Experiment handle class."""

    def __init__(self) -> None:
        self.exitFlag: bool = False

        # [D1] Pause control. Event SET means "running"; CLEARED means
        # "paused". The worker blocks in pauseCheck() while cleared.
        self.pauseEvent = threading.Event()
        self.pauseEvent.set()

        # [D3] Results, replacing assignin('base', ...)
        self.dataConf: Any = None
        self.Pawt: Optional[np.ndarray] = None
        self.HCawt: Optional[np.ndarray] = None
        self.resultsFile: Optional[str] = None

    # ------------------------------------------------------------------
    # Control API used by the GUI (thread-safe)
    # ------------------------------------------------------------------
    def requestPause(self) -> None:
        self.pauseEvent.clear()

    def requestResume(self) -> None:
        self.pauseEvent.set()

    def requestExit(self) -> None:
        """Stop the run; also wakes a paused worker so it can exit."""
        self.exitFlag = True
        self.pauseEvent.set()

    # ------------------------------------------------------------------
    # Main driver (port of Experiment.run)
    # ------------------------------------------------------------------
    def run(self, startData: Any, app: Any = None) -> Any:
        # The GUI builds startData as a dict; the engine classes use
        # attribute access (startData.doorOpeningTime, ...). Normalize.
        if isinstance(startData, dict):
            startData = SimpleNamespace(**startData)

        controller = Controller(startData.decisionMaker)
        dataConf = DataConf(startData)
        numMaxConfs = SimpleNamespace(
            Nbc=len(dataConf.BUILDING),
            Ncc=len(dataConf.CAR),
            Nicc=len(dataConf.TRAFFIC),
            Nifc=len(dataConf.TRAFFIC[0]) if len(dataConf.TRAFFIC) else 0,
        )
        simulator = Simulator(startData, numMaxConfs)

        for nbc in range(1, numMaxConfs.Nbc + 1):            # building confs
            building = dataConf.BUILDING[nbc - 1]
            for ncc in range(1, numMaxConfs.Ncc + 1):        # car confs
                cars = dataConf.CAR[ncc - 1]
                for iccIndex in range(1, numMaxConfs.Nicc + 1):   # incoming
                    for ifcIndex in range(1, numMaxConfs.Nifc + 1):  # interfloor
                        traffic = dataConf.TRAFFIC[iccIndex - 1][ifcIndex - 1]
                        if traffic is None:  # invalid traffic combination
                            continue

                        traffic.setRouteProbability(building)
                        controller.setTraffic(traffic)

                        for nsc in range(1, simulator.numSimulations + 1):
                            indices = SimpleNamespace(
                                nbc=nbc, ncc=ncc,
                                int=ifcIndex, inc=iccIndex, nsc=nsc)
                            simulator.confIndices = indices
                            simulator.totalRunCounter += 1

                            cars, HC, P = self.resetVariables(
                                simulator, building, cars, dataConf,
                                traffic, indices)

                            simulator.displayTraffic(
                                building, traffic, cars, HC, P, app, nsc)
                            time.sleep(1)  # MATLAB pause(1): hold first frame

                            # While a car is transferring/moving/has work,
                            # passengers wait, or sim time hasn't run out.
                            while self._simulationActive(simulator, cars, P):
                                t0 = time.perf_counter()  # tic

                                simulator.checkNewPassenger(HC, P, traffic)

                                # New passenger arrived or redispatch period
                                if (_atPeriod(simulator.time, simulator.arrivalRate)
                                        or _atPeriod(simulator.time,
                                                     simulator.decisionPeriod)):
                                    controller.runDecisionProcess(
                                        building, cars, HC, P)

                                simulator.displayTraffic(
                                    building, traffic, cars, HC, P, app, nsc)
                                controller.operate(cars, simulator, HC, P)
                                controller.updateCarStatesForNextDecision(cars)
                                # [D2] drawnow removed - UI updates flow
                                # through signals, not this thread.

                                if self.exitFlag:
                                    return None
                                self.pauseCheck(app)
                                if self.terminationCheck(app):
                                    return None

                                simulator.totalRunTime += (
                                    time.perf_counter() - t0)  # toc

                            simulator.recordData(HC, P, cars, dataConf, indices)

                        simulator.displayTraffic(
                            building, traffic, cars, HC, P, app, nsc)

        # [D3] replaces assignin("base","dataConf",dataConf)
        self.dataConf = dataConf
        self.Pawt, self.HCawt, self.resultsFile = Experiment.saveResults(
            dataConf, numMaxConfs, simulator.numSimulations)
        return dataConf

    @staticmethod
    def _simulationActive(simulator: Any, cars: List[Any], P: Any) -> bool:
        """Port of the while-condition in Experiment.run.

        [D10] Phased alighting (car.py [A1]): between beginDropoff and the
        door-open moment, the pending work is represented only by the
        stop-over counter. When doorClosingTime + passengerTransferTime
        == 0 the alight lands exactly when the counter reaches 0, so the
        original condition could exit the loop one tick early and strand
        passengers in 'travelling' (never served). The pendingAlight /
        alighting terms keep the loop alive through the alight and the
        sprite clean-up; in ordinary door configurations they are only
        non-empty while the counter is non-zero, so they change nothing.
        The pendingBoard / boarding terms ([A4]) are the mirror for the
        boarding side (pendingBoard is doubly covered by P.waiting).
        """
        return (
            any(c.stopOverCounter for c in cars)
            or any(c.DF for c in cars)          # non-empty destination sets
            or any(c.state for c in cars)
            or any(c.pendingAlight or c.alighting
                   or c.pendingBoard or c.boarding for c in cars)   # [D10]
            or (simulator.arrivalRate != 0
                and not math.isinf(simulator.arrivalRate)
                and simulator.time < Simulator.getSetEndTime())
            or bool(P.waiting[1])
            or bool(P.waiting[2])
        )

    # ------------------------------------------------------------------
    # Per-simulation reset (port of Experiment.resetVariables)
    # ------------------------------------------------------------------
    def resetVariables(self, simulator: Any, building: Any, cars: List[Any],
                       dataConf: Any, traffic: Any, indices: SimpleNamespace
                       ) -> Tuple[List[Any], Any, Any]:
        simulator.time = 0          # reset simulation time
        Passenger.reset_id()         # reset static Passenger id
        HallCall.reset_id()          # reset static HallCall id

        if simulator.dataType in (1, 2):   # 1: New Data  2: Recorded Data
            HC = HallCallLists()
            # Detach from the template stored in dataConf.CAR
            # (MATLAB: cars(i) = copy(cars(i)))
            cars = [copy.deepcopy(c) for c in cars]

            if len(cars) > 1:
                # Evenly distributed starting floors
                floors = np.round(
                    np.linspace(1, building.nf, len(cars))).astype(int)
                for car, fl in zip(cars, floors):
                    car.floor = float(fl)
            elif len(cars) == 1:
                # [D6] MATLAB: cars(1).floor = 1; randi(building.nf);
                # randi(...) is dead code; floor pinned to 1 on purpose.
                cars[0].floor = 1.0

            for c in cars:
                c.reset()

            if simulator.dataType == 1:      # new data
                P = PassengerLists()
                for _ in range(Traffic.getSetNumInitialPassengers()):
                    simulator.generatePassenger(HC, P, traffic)
            else:                            # recorded data
                rec = dataConf.RECold[recKey(
                    indices.nbc, indices.ncc,
                    indices.inc, indices.int, indices.nsc)]
                P = copy.deepcopy(rec.P)
                # Load P_waiting from P_served
                simulator.checkNewPassenger(HC, P, traffic)

        else:                                 # 3: new data, custom initials
            cars = copy.deepcopy(dataConf.initialCars)
            P = copy.deepcopy(dataConf.initialP)
            HC = copy.deepcopy(dataConf.initialHC)

        return cars, HC, P

    # ------------------------------------------------------------------
    # Pause / termination (ports of pauseCheck / terminationCheck)
    # ------------------------------------------------------------------
    def pauseCheck(self, app: Any = None) -> None:
        """
        [D1] Same role as MATLAB pauseCheck: the point in the loop where
        the Pause button freezes the traffic-flow animation until
        Continue is pressed, while Terminate stays possible.

        The MATLAB busy-wait (pause(0.001) polling) is replaced by a
        blocking Event wait, which is the idiomatic (and cheaper)
        mechanism now that the experiment runs off the GUI thread.
        requestExit() sets the event, so a paused run unblocks here and
        is then stopped by the terminationCheck that follows.
        """
        self.pauseEvent.wait()

    def terminationCheck(self, app: Any = None) -> bool:
        """
        [D5] Only the stop *decision* lives here now. The axes clean-up
        MATLAB performed in this method is widget work and must run on
        the GUI thread - it moved to the GUI's Terminate slot.
        Accepts both stop_flag (this project's GUI) and stopFlag.
        """
        if self.exitFlag:
            return True
        if app is None:
            return False
        return bool(getattr(app, "stop_flag", getattr(app, "stopFlag", False)))

    # ------------------------------------------------------------------
    # Results export (port of static saveResults)
    # ------------------------------------------------------------------
    @staticmethod
    def saveResults(dataConf: Any, numMaxConfs: SimpleNamespace, NS: int,
                    outputDir: str = ".") -> Tuple[np.ndarray, np.ndarray, str]:
        import pandas as pd  # local import: only needed at save time

        Nbc, Ncc = numMaxConfs.Nbc, numMaxConfs.Ncc
        Nicc, Nifc = numMaxConfs.Nicc, numMaxConfs.Nifc

        Pawt = np.zeros((Nbc, Ncc, Nicc, Nifc))
        HCawt = np.zeros((Nbc, Ncc, Nicc, Nifc))  # MATLAB grew this implicitly

        nFloorMin = dataConf.BUILDING[0].nf
        nFloorMax = dataConf.BUILDING[Nbc - 1].nf
        nCarMin = len(dataConf.CAR[0])
        nCarMax = len(dataConf.CAR[Ncc - 1])

        # [D8] Traffic sweep labels. MATLAB read TRAFFIC{1,1}.inc and
        # TRAFFIC{end,end}.inc directly - the corner cells can be EMPTY
        # (inc + int > 100 combos), which errors in MATLAB for range
        # sweeps. The sweep step is fixed at 10 in generateTrafficConf,
        # so min values come from the first non-empty cell and the max
        # values follow arithmetically from the grid dimensions.
        step = 10  # TRAFFIC_SWEEP_STEP in configuration.py
        t0_i, t0_j, t0 = next(
            ((i, j, t) for i, row in enumerate(dataConf.TRAFFIC)
             for j, t in enumerate(row) if t is not None))
        incomingMin = t0.inc - step * t0_i
        interfloorMin = t0.int - step * t0_j
        incomingMax = incomingMin + step * (Nicc - 1)
        interfloorMax = interfloorMin + step * (Nifc - 1)

        # Same name as MATLAB sprintf (incl. the missing dash before
        # 'IncomingTraffic', kept for byte-compatible filenames).
        fileName = (
            f"NumFloors-{nFloorMin}-{nFloorMax}-NumCars-{nCarMin}-{nCarMax}"
            f"IncomingTraffic-{incomingMin}-{incomingMax}"
            f"-InterfloorTraffic-{interfloorMin}-{interfloorMax}"
            f"-NumSims-{NS}.xlsx")
        filePath = os.path.join(outputDir, fileName)

        # [D8] MATLAB built these with step 1 (incomingMin:incomingMax),
        # which mismatches the table's Nicc/Nifc dimensions whenever a
        # range is swept (array2table would error). Step-10 names align
        # with the grid.
        rowNames = [f"Incoming_{incomingMin + step * i}" for i in range(Nicc)]
        colNames = [f"Interfloor_{interfloorMin + step * j}"
                    for j in range(Nifc)]

        with pd.ExcelWriter(filePath, engine="openpyxl") as writer:
            for nbc in range(1, Nbc + 1):
                nfloor = dataConf.BUILDING[nbc - 1].nf
                for ncc in range(1, Ncc + 1):
                    ncars = len(dataConf.CAR[ncc - 1])
                    PawtTable = np.zeros((Nicc, Nifc))
                    HCawtTable = np.zeros((Nicc, Nifc))
                    PboardTable = np.zeros((Nicc, Nifc))

                    for icc in range(1, Nicc + 1):
                        for ifc in range(1, Nifc + 1):
                            tempPawt: List[float] = []
                            tempHCawt: List[float] = []
                            tempPboard: List[float] = []
                            for ns in range(1, NS + 1):
                                # [D8] Invalid traffic combos (inc+int>100)
                                # never produce a record; MATLAB would hit
                                # an empty cell and error. NaN instead.
                                rec = dataConf.RECnew.get(
                                    recKey(nbc, ncc, icc, ifc, ns))
                                if rec is None:
                                    tempPawt.append(float("nan"))
                                    tempHCawt.append(float("nan"))
                                    tempPboard.append(float("nan"))
                                    continue
                                p_up = rec.P.served[1]
                                p_down = rec.P.served[2]
                                hc_up = rec.HC.served[1]
                                hc_down = rec.HC.served[2]
                                pw = [p.WT for p in list(p_up) + list(p_down)
                                      if p.QJT != -1]
                                hw = [h.WT for h in list(hc_up) + list(hc_down)
                                      if h.QJT != -1]
                                pb = [p.WT_board for p in list(p_up) + list(p_down)
                                      if p.QJT != -1]
                                # MATLAB mean([]) is NaN
                                tempPawt.append(
                                    float(np.mean(pw)) if pw else float("nan"))
                                tempHCawt.append(
                                    float(np.mean(hw)) if hw else float("nan"))
                                tempPboard.append(
                                    float(np.mean(pb)) if pb else float("nan"))

                            m_p = float(np.mean(tempPawt))
                            m_h = float(np.mean(tempHCawt))
                            Pawt[nbc - 1, ncc - 1, icc - 1, ifc - 1] = m_p
                            PawtTable[icc - 1, ifc - 1] = m_p
                            HCawt[nbc - 1, ncc - 1, icc - 1, ifc - 1] = m_h
                            HCawtTable[icc - 1, ifc - 1] = m_h
                            PboardTable[icc - 1, ifc - 1] = float(np.mean(tempPboard))

                    Tp = pd.DataFrame(PawtTable, index=rowNames,
                                      columns=colNames)
                    Tp.index.name = "Average Passenger Waiting Time"
                    Thc = pd.DataFrame(HCawtTable, index=rowNames,
                                       columns=colNames)
                    Thc.index.name = "Average Hall Call Waiting Time"
                    Tboard = pd.DataFrame(PboardTable, index=rowNames, columns=colNames)
                    Tboard.index.name = "Average Passenger Wait to Boarding"

                    sheetName = f"NumFloors-{nfloor}-NumCars-{ncars}"
                    Tp.to_excel(writer, sheet_name=sheetName)
                    # MATLAB: Range A{rows+3} (1-indexed) -> startrow rows+2
                    Thc.to_excel(writer, sheet_name=sheetName,
                                 startrow=len(Tp) + 2)
                    Tboard.to_excel(writer, sheet_name=sheetName,
                                    startrow=2 * (len(Tp) + 2))

            # Keep the existing first two tables/return signature compatible.
            # The additional table and definitions distinguish new metrics from
            # historical full-open WT results; old workbooks are not converted.
            pd.DataFrame([
                ("Passenger WT", "Queue join to opening start of the car that accepts "
                 "the passenger; zero if joining its opening/open phase."),
                ("Passenger wait to boarding", "WT_board = BT - QJT; boarding at fully-open doors."),
                ("Hall-call WT", "Unchanged call-response timing; not passenger weighted."),
                ("BT / DAT / TrT / TTD", "Unchanged animation events; "
                 "TTD = WT_board + TrT, not generally WT + TrT."),
            ], columns=["Metric", "Definition (seconds)"]).to_excel(
                writer, sheet_name="Metric definitions", index=False)

        return Pawt, HCawt, filePath
