"""
analysis/headless_benchmark.py
==============================
Deterministic, headless end-to-end runs of the real engine (Experiment ->
Controller -> dispatcher -> Car physics) that print one metrics row per run.
Run it on two revisions and diff the output to see what an engine change does.

    python analysis/headless_benchmark.py              # full table
    python analysis/headless_benchmark.py --quick      # scenarios only

Rows:
  * every initials_files/*.xlsx snapshot (dataType=3, no arrivals) with the
    Nearest Car dispatcher, once with the default "dispatch when new call
    registered" setting (one decision at t=0) and once re-dispatching every
    tick (decisionPeriod=1); the seeded GA (Destination/WT objective) is
    attempted with decisionPeriod=1 as well, but objFunDestination (like the
    exact dispatcher) rejects a snapshot taken while a pickup is pending
    boarding, so that row reports the rejection - GA/exact results are
    one-shot by construction and cannot see the pre-boarding window;
  * Poisson-free periodic traffic (dataType=1, one arrival every
    `arrivalRate` s drawn from the route matrix) with the Nearest Car
    dispatcher for a few NumPy seeds.

Metrics are taken from the recorded run: served passengers (unique ids),
duplicate served entries (`dup` > 0 means a passenger was boarded by two cars
- a pre-existing [A4] race, see the pull request that added this script),
unserved count, mean primary WT (pickup door-opening start), mean WT_board,
mean transit time, mean time-to-destination, and the last destination
arrival time.
Physics: ga_sweep_config.CAR_PARAMS (doors 2+3+2, capacity 10, 0.5 floor/s).
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
from types import SimpleNamespace as NS

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import experiment as experiment_module                     # noqa: E402
from data_conf import recKey                               # noqa: E402
from data_structures.hall_call import HallCall             # noqa: E402
from data_structures.passenger import Passenger            # noqa: E402
from decision import NearestCarDispatcher                  # noqa: E402
from decision.meta import GA                               # noqa: E402
from decision.meta.obj_funs import objFunDestination       # noqa: E402
from experiment import Experiment                          # noqa: E402
from ga_sweep_config import CAR_PARAMS                     # noqa: E402
from simulator import Simulator                            # noqa: E402

FIXED = NS(stateUpdateTypeForNextDecision="fixed")


def nearest():
    return NearestCarDispatcher(FIXED)


def ga(seed=2026, G=20, nPop=20):
    return GA(NS(stateUpdateTypeForNextDecision="fixed", G=G, nPop=nPop,
                 mutationFunction="uniform", parameterSearch=False,
                 numberOfRuns=1, seed=seed, Pc=0.8, Pm=0.1,
                 crossoverFcn="crossoverscattered",
                 selectionFcn="selectionstochunif", objFun=objFunDestination))


def _metrics(record):
    entries = record.P.served[1] + record.P.served[2]
    served = list({p.id: p for p in entries}.values())     # one row per passenger
    unserved = (len(record.P.waiting[1]) + len(record.P.waiting[2])
                + len(record.P.travelling[1]) + len(record.P.travelling[2]))
    done = [p for p in served if p.DAT is not None]
    m = lambda xs: float(np.mean(xs)) if xs else float("nan")       # noqa: E731
    return dict(
        served=len(served), dup=len(entries) - len(served), unserved=unserved,
        WT=m([p.WT for p in served]),
        WT_board=m([p.WT_board for p in served]),
        TrT=m([p.TrT for p in done]),
        TTD=m([p.TTD for p in done]),
        last_DAT=max((p.DAT for p in done), default=float("nan")),
    )


def _run(start, end_time):
    """Run like the GUI does, with display and pacing off."""
    Passenger.reset_id()
    HallCall.reset_id() if hasattr(HallCall, "reset_id") else None
    saved = (Simulator._speed, Simulator._displayTrafficFlow,
             Simulator._displayTabularData, Simulator._endTime,
             experiment_module.time.sleep)
    old_cwd = os.getcwd()
    tmp = tempfile.TemporaryDirectory(prefix="esra_bench_")   # result .xlsx goes here, not into the repo
    try:
        Simulator._speed = None
        Simulator.getSetDisplayTrafficFlow(False)
        Simulator.getSetDisplayTabularData(False)
        Simulator.getSetEndTime(end_time)
        experiment_module.time.sleep = lambda _s: None
        os.chdir(tmp.name)
        exp = Experiment()
        conf = exp.run(start, app=None)
        return conf.RECnew[recKey(1, 1, 1, 1, 1)]
    finally:
        os.chdir(old_cwd)
        tmp.cleanup()
        (Simulator._speed, Simulator._displayTrafficFlow,
         Simulator._displayTabularData, Simulator._endTime,
         experiment_module.time.sleep) = saved


def snapshot_run(workbook, decision_maker, decision_period):
    start = NS(dataType=3, fileName=workbook, decisionMaker=decision_maker,
               refTime=0, endTime=0, arrivalRate=float("inf"),
               decisionPeriod=decision_period, numSimulations=1,
               stateUpdateTypeForNextDecision="fixed", **CAR_PARAMS)
    return _metrics(_run(start, 0))


def traffic_run(seed, nf=8, nc=3, arrival_rate=5, end_time=600, inc=30, int_=40,
                initial=2, decision_period=float("inf")):
    np.random.seed(seed)                       # simulator.generatePassenger uses np.random.rand
    start = NS(dataType=1, decisionMaker=nearest(), numSimulations=1,
               stateUpdateTypeForNextDecision="fixed",
               arrivalRate=arrival_rate, decisionPeriod=decision_period,
               NFmin=nf, NFmax=nf, NFstep=1, NCmin=nc, NCmax=nc,
               parkingAlgorithm="Park1 (No parking method)",
               INCmin=inc, INCmax=inc, INTmin=int_, INTmax=int_,
               numInitialPassengers=initial, refTime=0, endTime=end_time,
               **CAR_PARAMS)
    return _metrics(_run(start, end_time))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="snapshot scenarios only")
    ap.add_argument("--seeds", type=int, default=5, help="traffic seeds (default 5)")
    args = ap.parse_args()

    cols = ["served", "dup", "unserved", "WT", "WT_board", "TrT", "TTD", "last_DAT"]
    print(f"{'run':52s} " + " ".join(f"{c:>9s}" for c in cols))

    def row(label, m):
        print(f"{label:52s} " + " ".join(
            f"{m[c]:9d}" if isinstance(m[c], int) else f"{m[c]:9.3f}" for c in cols))
        sys.stdout.flush()

    for wb in sorted(glob.glob(os.path.join(ROOT, "initials_files", "*.xlsx"))):
        name = os.path.basename(wb).replace("initials_file_", "").replace(".xlsx", "")
        name = "S1" if name == "initials_file" else name
        row(f"{name:8s} nearest  decision@t0", snapshot_run(wb, nearest(), float("inf")))
        row(f"{name:8s} nearest  period=1", snapshot_run(wb, nearest(), 1))
        try:
            row(f"{name:8s} GA(2026) period=1", snapshot_run(wb, ga(), 1))
        except ValueError as exc:           # objFunDestination refuses pending-boarding snapshots
            print(f"{name:8s} GA(2026) period=1".ljust(52) + f" rejected: {exc}")
    if args.quick:
        return
    for seed in range(1, args.seeds + 1):
        row(f"traffic nf8 nc3 rate5 600s seed={seed} nearest", traffic_run(seed))
        row(f"traffic nf8 nc3 rate5 600s seed={seed} nearest period=1",
            traffic_run(seed, decision_period=1))


if __name__ == "__main__":
    main()
