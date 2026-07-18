import os
import sys
import threading
import time
"""
tests/test_experiment_smoke.py
===============================
Run from the ESRA/ root:  python tests/test_experiment_smoke.py

Verifies with stub engine classes that the Experiment port:
  1. runs the sweep + simulation loop to completion,
  2. records data and writes the results .xlsx (both tables per sheet),
  3. pauseCheck blocks while paused and wakes on resume,
  4. requestExit() interrupts a paused run (terminate-while-paused).
"""


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs"))

import engine_stubs  # noqa: F401  (installs stub modules BEFORE experiment import)
from experiment import Experiment, _atPeriod


CAR_PARAMS = dict(doorOpeningTime=2, passengerTransferTime=3,
                  doorClosingTime=2, carCapacity=10, carCapacityFactor=1.0,
                  carVelocity=1.5, floorHeight=3.0)


def _startData(**overrides):
    """Full startData with every field the real Car/configuration need."""
    from types import SimpleNamespace as _NS
    from decision import NearestCarDispatcher
    base = {"stateUpdateTypeForNextDecision": "fixed",
            "decisionMaker": NearestCarDispatcher(
                _NS(stateUpdateTypeForNextDecision="fixed")), "numSimulations": 2,
            "arrivalRate": float("inf"), "decisionPeriod": float("inf"),
            "dataType": 1, "NFmin": 5, "NFmax": 5, "NFstep": 1,
            "NCmin": 2, "NCmax": 2,
            "parkingAlgorithm": "Park1 (No parking method)",
            "INCmin": 30, "INCmax": 30, "INTmin": 40, "INTmax": 40,
            "numInitialPassengers": 1, "refTime": 0, "endTime": 15,
            **CAR_PARAMS}
    base.update(overrides)
    return base


def _run(exp, start):
    """Run like the GUI does: set the Simulator statics the MATLAB start
    callback set (end time; speed/display flags stay off for headless
    tests), with the pause(1) frame hold shortened."""
    from simulator import Simulator
    Simulator.getSetEndTime(start["endTime"])
    real_sleep = time.sleep
    time.sleep = lambda s: real_sleep(min(s, 0.01))
    try:
        return exp.run(start, app=None)
    finally:
        time.sleep = real_sleep


def test_atPeriod():
    import math
    assert _atPeriod(0, math.inf)
    assert not _atPeriod(5, math.inf)
    assert _atPeriod(10, 5)
    assert _atPeriod(0.30000000000000004, 0.1)  # float accumulation case
    assert not _atPeriod(3, 2)
    assert _atPeriod(0, 0) and not _atPeriod(1, 0)
    print("PASS  _atPeriod float-safe period check")


def test_full_run(tmpdir="."):
    exp = Experiment()
    start = _startData()

    # speed up: skip MATLAB's pause(1) frame hold during the test
    dataConf = _run(exp, start)

    assert dataConf is not None
    assert len(dataConf.RECnew) == 2, "one record per simulation expected"
    assert exp.Pawt is not None and exp.Pawt.shape == (1, 1, 1, 1)
    assert exp.Pawt[0, 0, 0, 0] == 2.0, \
        "user Dispatcher.run updates states in the decision step, so the " \
        "car moves the same tick it is assigned: boarding at t=2"
    assert os.path.exists(exp.resultsFile)

    # Real Car + real Controller trip physics (per simulation):
    from data_conf import recKey
    rec = dataConf.RECnew[recKey(1, 1, 1, 1, 1)]
    car1 = rec.cars[0]
    assert car1.numOfServedPassengers == 1 and car1.load == 0
    assert car1.numOfStops == 2, "one stop at pickup, one at destination"
    assert car1.floor == 4.0 and car1.state == 0 and not car1.DF
    assert car1.tripTime == 6.0, "2 moves to pickup + 4 moves to floor 4"
    p = rec.P.served[1][0]
    assert (p.BT, p.DAT, p.TrT) == (2, 13, 11)
    assert rec.HC.served[1][0].WT == 2.0

    import openpyxl
    wb = openpyxl.load_workbook(exp.resultsFile)
    ws = wb[wb.sheetnames[0]]
    assert ws["A1"].value == "Average Passenger Waiting Time"
    assert ws["B1"].value == "Interfloor_40"
    assert ws["A2"].value == "Incoming_30"
    assert ws["B2"].value == 2.0
    # second table starts len(Tp)+2 rows below (0-indexed) -> row 4 (1-indexed)
    assert ws["A4"].value == "Average Hall Call Waiting Time"
    assert ws["B5"].value == 2.0
    print(f"PASS  full run -> {os.path.basename(exp.resultsFile)}")
    os.remove(exp.resultsFile)


def test_pause_resume():
    exp = Experiment()
    exp.requestPause()

    unblocked = threading.Event()

    def worker():
        exp.pauseCheck(None)  # must block here
        unblocked.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    time.sleep(0.15)
    assert not unblocked.is_set(), "pauseCheck must block while paused"

    exp.requestResume()
    t.join(timeout=1)
    assert unblocked.is_set(), "pauseCheck must return after resume"
    print("PASS  pauseCheck blocks on pause, wakes on resume (no busy-wait)")


def test_terminate_while_paused():
    exp = Experiment()
    exp.requestPause()

    result = {}

    def worker():
        exp.pauseCheck(None)                 # blocked...
        result["terminated"] = exp.terminationCheck(None)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    time.sleep(0.15)
    assert t.is_alive(), "worker should be parked in pauseCheck"

    exp.requestExit()                        # Terminate pressed while paused
    t.join(timeout=1)
    assert result.get("terminated") is True
    print("PASS  Terminate interrupts a paused run")


def test_recorded_roundtrip():
    """dataType=1 run -> saveDataConf -> DataConf(dataType=2) reload:
    RECnew moves to RECold, RECnew empties, end time -> 0, nsc recovered,
    and resetVariables serves passengers from a deep copy of RECold."""
    from types import SimpleNamespace
    from data_conf import DataConf, saveDataConf, recKey
    from simulator import Simulator as StubSimulator

    StubSimulator.getSetEndTime(3)  # restore, in case a prior test changed it

    exp = Experiment()
    start = _startData()
    _run(exp, start)

    pkl = "recorded_test.pkl"
    saveDataConf(exp.dataConf, pkl)
    os.remove(exp.resultsFile)

    start2 = SimpleNamespace(dataType=2, fileName=pkl)
    dc2 = DataConf(start2)
    assert len(dc2.RECold) == 2 and len(dc2.RECnew) == 0
    assert StubSimulator.getSetEndTime() == 0, "case 2 must zero the end time"
    assert dc2.nsc == 2, "nsc = total / (nbc*ncc*nint*ninc)"

    # resetVariables (dataType=2) must deep-copy P out of RECold
    sim2 = StubSimulator(
        SimpleNamespace(dataType=2, numSimulations=2,
                        arrivalRate=float("inf"), decisionPeriod=float("inf"),
                        refTime=0, endTime=15),
        SimpleNamespace(Nbc=1, Ncc=1, Nicc=1, Nifc=1))
    idx = SimpleNamespace(nbc=1, ncc=1, inc=1, int=1, nsc=1)
    cars2, HC2, P2 = exp.resetVariables(sim2, dc2.BUILDING[0], dc2.CAR[0],
                                        dc2, dc2.TRAFFIC[0][0], idx)
    stored = dc2.RECold[recKey(1, 1, 1, 1, 1)].P
    assert P2 is not stored, "must be a deep copy, not the stored object"
    # real replay: the recorded passenger moved served -> waiting (as a
    # copy), and a fresh hall call was registered at its floor
    assert len(P2.waiting[1]) == 1 and len(P2.served[1]) == 0
    assert len(HC2.waiting[1]) == 1
    assert len(stored.served[1]) == 1, "RECold must stay untouched"
    assert P2.waiting[1][0] is not stored.served[1][0]

    # --- full replay: run a second experiment FROM the recording -------
    exp2 = Experiment()
    start2 = _startData(dataType=2, fileName=pkl)
    _run(exp2, start2)
    assert StubSimulator.getSetEndTime() == 0, "DataConf case 2 zeroes it"
    assert len(exp2.dataConf.RECnew) == 2, "both recorded sims replayed"
    assert exp2.Pawt[0, 0, 0, 0] == 2.0, \
        "replay must reproduce the recorded waiting time exactly"
    replayed = exp2.dataConf.RECnew[recKey(1, 1, 1, 1, 1)].P.served[1][0]
    assert (replayed.WT, replayed.BT, replayed.DAT) == (2, 2, 13)
    os.remove(exp2.resultsFile)

    os.remove(pkl)
    StubSimulator.getSetEndTime(3)  # restore for any later tests
    print("PASS  recorded-data round-trip (save -> DataConf case 2 -> reset)")


def test_sparse_ranged_traffic():
    """Ranged traffic (2x3 grid with 3 invalid combos) -> run skips the
    None cells, saveResults labels rows/cols with the 10-step grid [D8]
    and reports NaN for never-simulated combos [D9]. Both paths crashed
    in the MATLAB original."""
    import numpy as np
    import openpyxl
    from simulator import Simulator as StubSimulator
    StubSimulator.getSetEndTime(3)

    exp = Experiment()
    start = _startData(numSimulations=1,
                       INCmin=90, INCmax=100, INTmin=0, INTmax=20)
    _run(exp, start)

    # 3 valid combos: (90,0) (90,10) (100,0)
    assert len(exp.dataConf.RECnew) == 3
    assert exp.Pawt.shape == (1, 1, 2, 3)
    assert exp.Pawt[0, 0, 0, 0] == 2.0 and exp.Pawt[0, 0, 1, 0] == 2.0
    assert np.isnan(exp.Pawt[0, 0, 0, 2]), "invalid combo must be NaN"
    assert np.isnan(exp.Pawt[0, 0, 1, 1]) and np.isnan(exp.Pawt[0, 0, 1, 2])
    assert "Incoming-90-100" in exp.resultsFile.replace("Traffic", "")

    wb = openpyxl.load_workbook(exp.resultsFile)
    ws = wb[wb.sheetnames[0]]
    assert [ws.cell(1, c).value for c in (2, 3, 4)] == \
        ["Interfloor_0", "Interfloor_10", "Interfloor_20"], "[D8] 10-step labels"
    assert ws["A2"].value == "Incoming_90" and ws["A3"].value == "Incoming_100"
    assert ws["B2"].value == 2.0 and ws["B3"].value == 2.0
    assert ws["D2"].value is None and ws["C3"].value is None, "[D9] NaN cells"
    # second table: MATLAB rule rows+1+2 -> header on sheet row 5 here
    assert ws["A5"].value == "Average Hall Call Waiting Time"
    os.remove(exp.resultsFile)
    print("PASS  ranged sparse traffic: 10-step labels [D8], NaN combos [D9]")


def test_display_frames():
    """Enable the display statics, capture frames through a fake
    app.worker.frame signal, and check the frame contents that the GUI
    renders (flow section, car table, results, counters)."""
    from types import SimpleNamespace
    from simulator import Simulator

    frames = []
    fake_app = SimpleNamespace(worker=SimpleNamespace(
        frame=SimpleNamespace(emit=frames.append)))

    Simulator.getSetDisplayTrafficFlow(True)
    Simulator.getSetDisplayTabularData(True)
    Simulator.setgetSpeed(5)          # 0.1 ms/frame pacing during the test

    exp = Experiment()
    start = _startData(numSimulations=1)
    from simulator import Simulator as S
    S.getSetEndTime(start["endTime"])
    real_sleep = time.sleep
    time.sleep = lambda s: real_sleep(min(s, 0.001))
    try:
        exp.run(start, app=fake_app)
    finally:
        time.sleep = real_sleep
        Simulator.getSetDisplayTrafficFlow(False)
        Simulator.getSetDisplayTabularData(False)
        Simulator.setgetSpeed(None) if False else None

    assert len(frames) > 10, "one frame per loop step expected"
    mid = next(f for f in frames if f["flow"]["cars"][0]["load"] == 1
               and f["flow"]["cars"][0]["state"] == 1)
    assert mid["nf"] == 5 and mid["numCars"] == 2
    assert mid["traffic"] == {"inc": 30, "int": 40, "out": 30}
    assert mid["flow"]["cars"][0]["DF"] == [4]
    car_table = mid["tables"]["car"]
    assert car_table["columns"] == ["Car-1", "Car-2"]
    assert car_table["rows"][0] == "Car position"
    last = frames[-1]
    assert last["tables"]["results"][3] == "1", "1 served passenger"
    assert last["tables"]["results"][6] == "2.00", "avg passenger WT"
    assert len(last["counters"]) == 6
    os.remove(exp.resultsFile)
    globals()["_captured_frames"] = frames   # reused by the render demo
    print("PASS  displayTraffic frames: flow + tables + counters payloads")


def test_traffic_probabilities():
    """Real Traffic.setRouteProbability: structure, sums, edge cases,
    [T2] validations, and the shared static across subclasses."""
    import numpy as np
    from traffic import Traffic
    from building import Building

    t = Traffic(30, 40)
    assert t.out == 30 and t.confCounter == 0
    t.setRouteProbability(Building(5))
    assert t.confCounter == 1
    Pr, Pa = t.Pr, t.Pa

    assert Pr.shape == (5, 5) and np.isclose(Pr.sum(), 1.0)
    assert np.allclose(np.diag(Pr), 0), "[S4] same-floor diagonal is zero"
    assert np.allclose(Pr[0, 1:], 0.30 / 4), "incoming: lobby -> uniform"
    assert np.allclose(Pr[1:, 0], 0.30 / 4), "outgoing: floors -> lobby"
    interfloor = Pr[1:, 1:][~np.eye(4, dtype=bool)]
    assert np.allclose(interfloor, 0.40 / 3 / 4), "interfloor uniform"
    assert np.isclose(Pa[0], 0.30) and np.allclose(Pa[1:], 0.70 / 4)
    assert np.isclose(Pa.sum(), 1.0)

    # nf = 2 edge: MATLAB's `if nf > 2` guard (no division by zero)
    t2 = Traffic(50, 30)
    t2.setRouteProbability(Building(2))
    assert np.isclose(t2.Pr[1:, 1:].sum(), 0), "no interfloor with 2 floors"

    # alternative modes still produce distributions ([T1] prealloc)
    t3 = Traffic(20, 60)
    t3.setRouteProbability(Building(8), destProbSelection=2)
    # [T5] faithful MATLAB deficit: heavy floor emits no interfloor trips
    expected = 0.20 + 0.20 + 0.60 * 6 / 7
    assert np.isclose(t3.Pr.sum(), expected), "mode-2 mass deficit [T5]"
    assert np.allclose(np.diag(t3.Pr), 0)
    t3.setRouteProbability(Building(8), destProbSelection=3)
    assert np.isclose(t3.Pr.sum(), 1.0) and np.allclose(np.diag(t3.Pr), 0)

    # [T2] informative errors instead of MATLAB dimension crashes
    for kwargs in ({"destProbSelection": 2}, {"destProbSelection": 3}):
        try:
            Traffic(20, 60).setRouteProbability(Building(3), **kwargs)
            assert False, "expected ValueError"
        except ValueError:
            pass
    try:
        Traffic(20, 60).setRouteProbability(Building(5),
                                            arrivalProbSelection=2)
        assert False, "expected ValueError (6-floor hard-coding)"
    except ValueError:
        pass

    # static shared across subclasses (a MATLAB persistent is one slot)
    class Sub(Traffic):
        pass
    Sub.getSetNumInitialPassengers(7)
    assert Traffic.getSetNumInitialPassengers() == 7
    Traffic.getSetNumInitialPassengers(1)
    print("PASS  Traffic probabilities: structure, sums, edges, [T1]/[T2]")


def test_generate_passenger_distribution():
    """Seeded end-to-end sampling through the REAL Pr matrix: verifies
    simulator [S4]'s column-major (floor, DF) unravelling with an
    asymmetric traffic mix (a transposed mapping would swap the
    origin/destination shares)."""
    import numpy as np
    from traffic import Traffic
    from building import Building
    from simulator import Simulator
    from data_structures.hall_call_lists import HallCallLists
    from data_structures.passenger_lists import PassengerLists

    t = Traffic(50, 30)                  # out = 20: asymmetric on purpose
    t.setRouteProbability(Building(5))

    sim = object.__new__(Simulator)      # only .time is needed here
    sim.time = 0
    np.random.seed(0)
    HC, P = HallCallLists(), PassengerLists()
    floors, dests = [], []
    for _ in range(4000):
        sim.generatePassenger(HC, P, t)
    for d in (1, 2):
        for p in P.waiting[d]:
            floors.append(p.floor)
            dests.append(p.DF)
            assert p.floor != p.DF and 1 <= p.floor <= 5 and 1 <= p.DF <= 5

    origin_lobby = floors.count(1) / len(floors)
    dest_lobby = dests.count(1) / len(dests)
    assert abs(origin_lobby - 0.50) < 0.03, f"incoming share {origin_lobby}"
    assert abs(dest_lobby - 0.20) < 0.03, f"outgoing share {dest_lobby}"
    print("PASS  generatePassenger samples real Pr with correct orientation")


def test_nearest_car_fs():
    """FS categories, tie-breaks (incl. the MATLAB signed-d quirk), and
    multi-call assignment through the real dispatcher."""
    from types import SimpleNamespace as NS
    from decision import NearestCarDispatcher
    from building import Building
    from data_structures.hall_call import HallCall
    from data_structures.hall_call_lists import HallCallLists
    from data_structures.passenger_lists import PassengerLists
    from data_structures.passenger import Passenger

    disp = NearestCarDispatcher(NS(stateUpdateTypeForNextDecision="fixed"))
    nf = 10
    call_up_5 = HallCall(5, 0, 1)

    # category values
    away = NS(floor=7.0, state=1, stopOverCounter=0.0)       # above, going up
    assert disp.calculate_fs(call_up_5, away, nf, 5 - 7.0) == 1
    same_dir = NS(floor=2.0, state=1, stopOverCounter=0.0)   # below, going up
    assert disp.calculate_fs(call_up_5, same_dir, nf, 3.0) == nf + 1 - 3
    idle = NS(floor=8.0, state=0, stopOverCounter=0.0)
    assert disp.calculate_fs(call_up_5, idle, nf, -3.0) == nf - 3
    at_floor_opposite = NS(floor=5.0, state=-1, stopOverCounter=0.0)
    assert disp.calculate_fs(call_up_5, at_floor_opposite, nf, 0.0) == 1

    # end-to-end dispatch: signed-d tie-break prefers the car ABOVE
    def mini_car(cid, floor, state=0, soc=0.0):
        c = NS(id=cid, floor=float(floor), state=state, stopOverCounter=soc)
        c.updateServiceList = lambda HC, P: None
        c.updateAboveBelowHCs = lambda: None   # base run's step 3
        c.updateState = lambda t: None
        return c

    HC, P = HallCallLists(), PassengerLists()
    HC.add(HallCall(5, 0, 1))
    p = Passenger(5, 0, 8)
    P.waiting[1].append(p)
    cars = [mini_car(1, 2), mini_car(2, 8)]      # both idle, |d| = 3 tie
    disp.run(Building(nf), cars, HC, P)
    assert HC.waiting[1][0].carId == 2, "tie -> car above (signed d quirk)"
    assert p.carId == 2, "passenger follows the hall call's assignment"

    # stopOverCounter tie-break: same signed d, busier car loses
    HC2, P2 = HallCallLists(), PassengerLists()
    HC2.add(HallCall(5, 0, 1))
    cars2 = [mini_car(1, 8, soc=4.0), mini_car(2, 8, soc=0.0)]
    disp.run(Building(nf), cars2, HC2, P2)
    assert HC2.waiting[1][0].carId == 2, "smaller stopOverCounter wins tie"

    # two simultaneous calls -> different nearest cars, FS matrix stored
    HC3, P3 = HallCallLists(), PassengerLists()
    HC3.add(HallCall(2, 0, 1))
    HC3.add(HallCall(9, 0, 1))
    cars3 = [mini_car(1, 1), mini_car(2, 10)]
    disp.run(Building(nf), cars3, HC3, P3)
    assigned = [hc.carId for hc in HC3.waiting[1]]
    assert assigned == [1, 2]
    assert len(disp.FS[1]) == 2 and len(disp.FS[1][0]) == 2
    print("PASS  NearestCar FS: categories, both tie-breaks, multi-call")


def test_stop_flag_from_app():
    exp = Experiment()

    class FakeApp:
        stop_flag = True

    assert exp.terminationCheck(FakeApp()) is True
    print("PASS  terminationCheck reads app.stop_flag")


if __name__ == "__main__":
    test_atPeriod()
    test_full_run()
    test_pause_resume()
    test_terminate_while_paused()
    test_recorded_roundtrip()
    test_sparse_ranged_traffic()
    test_display_frames()
    test_traffic_probabilities()
    test_generate_passenger_distribution()
    test_nearest_car_fs()
    test_stop_flag_from_app()
    print("\nAll smoke tests passed.")
