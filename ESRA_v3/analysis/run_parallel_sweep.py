"""
analysis/run_parallel_sweep.py
===============================
Parallel GA parameter-search runner for the shared workstation.

Runs the exact GA.m sweep grid (GA.PARAM_SEARCH_GRID: 6 Pc x 5 Pm x
3 selection x 3 crossover x 5 mutation) x --runs repetitions as
independent (configuration, run) tasks across a process pool, on the
custom-initials dispatch snapshot (dataType 3 workbook).

Shared-server etiquette (defaults):
  * workers = physical cores - 1  (logical/2 - 1; --workers overrides)
  * every worker drops itself to BELOW-NORMAL process priority, so any
    co-worker's normal-priority job automatically preempts the sweep
  * numeric libraries pinned to 1 thread per worker (no oversubscription)

Reproducibility / seeding (--seed-mode):
  crn (default)  run r of EVERY configuration uses seed base+r ->
                 common random numbers: identical initial populations
                 per run index across configurations, enabling PAIRED
                 statistics (Wilcoxon signed-rank, valid Friedman).
  independent    every task gets its own seed (base + task index),
                 like the original MATLAB sweep.

Output (same names/format as the [P36] auto-save, so
analyze_ga_parameter_search.py and export_mat_to_csv.py work on it
unchanged):
  matlab_src/results/ga_param_search_parallel_<stamp>.npz  (+ .mat)
      fitnesses       (6,5,3,3,5,runs)  best cost per run [s]
      mean_fitnesses  (6,5,3,3,5)       mean over runs
  ..._meta.json       objective, budget, seeds, workers, elapsed, host
Ctrl+C saves whatever finished so far (unfinished cells = NaN,
filename suffixed _partial).

Usage (from the ESRA_v3/ root):
    .venv/Scripts/python analysis/run_parallel_sweep.py
        [--objective destination|conventional] [--runs 10]
        [--pop 100] [--gens 50] [--workers N] [--seed 0]
        [--seed-mode crn|independent] [--initials PATH] [--smoke]
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import copy
import ctypes
import datetime
import json
import multiprocessing as mp
import platform
import sys
import time
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_XLSX = os.path.join(ROOT, "matlab_src", "initials_file.xlsx")
DEFAULT_OUT = os.path.join(ROOT, "matlab_src", "results")

# Building & Car tab DEFAULTS for the snapshot cars; the GUI launcher
# overrides them with the tab's live values via the CLI flags below.
CAR_PARAMS = dict(doorOpeningTime=2.0, passengerTransferTime=3.0,
                  doorClosingTime=2.0, carCapacity=10,
                  carCapacityFactor=1.0, carVelocity=1.5,
                  floorHeight=3.0)

SMOKE_GRID = {                       # tiny grid for --smoke self-test
    "crossoverValues": [0.5, 0.8],
    "mutationValues": [0.1],
    "selectionFunctions": ["selectiontournament"],
    "crossoverFunctions": ["crossoverscattered"],
    "mutationFunctions": ["uniform", "swap"],
}

# ---- worker side ------------------------------------------------------
_W: NS | None = None                 # per-worker snapshot + settings


def _lowerPriority() -> None:
    """BELOW-NORMAL on Windows, nice +10 elsewhere; never fatal."""
    try:
        if os.name == "nt":
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass


def _initWorker(xlsxPath: str, objectiveName: str,
                popSize: int, generations: int,
                carParams: dict) -> None:
    """Runs once per worker process: set priority, load the snapshot."""
    global _W
    _lowerPriority()
    from data_conf import DataConf
    from decision.meta.obj_funs import (objFunConventional1,
                                        objFunDestination)

    dc = DataConf(NS(dataType=3, fileName=xlsxPath, **carParams))
    HC_1 = [hc.floor for hc in dc.initialHC.waiting[1]]
    HC_2 = [hc.floor for hc in dc.initialHC.waiting[2]]
    _W = NS(cars=dc.initialCars, P=dc.initialP,
            HC_all=HC_1 + HC_2, numofups=len(HC_1),
            nf=dc.BUILDING[0].nf,
            objFun=(objFunDestination if objectiveName == "destination"
                    else objFunConventional1),
            popSize=popSize, generations=generations)


def _runTask(task):
    """One GA execution: ((i1..i5), runIdx, seed, Pc, Pm, sel, xo, mut)."""
    idx, runIdx, seed, Pc, Pm, selFcn, xoverFcn, mutFcn = task
    from decision.meta.ga import GA

    w = _W

    def wrapper(population):
        # the [P14] dispatch wrapper: fresh deep copies per evaluation
        return w.objFun([copy.deepcopy(c) for c in w.cars],
                        w.HC_all, w.numofups, population, w.nf, w.P, "WT")

    disp = GA(NS(stateUpdateTypeForNextDecision="fixed",
                 G=w.generations, nPop=w.popSize,
                 mutationFunction=mutFcn, parameterSearch=False,
                 numberOfRuns=1, rng=np.random.default_rng(seed),
                 Pc=Pc, Pm=Pm, crossoverFcn=xoverFcn,
                 selectionFcn=selFcn, paramSearchSaveDir=None))
    disp.nVar, disp.maxLabel = len(w.HC_all), len(w.cars)
    _, bestCost = disp.optimize(wrapper)
    return idx, runIdx, float(bestCost)


# ---- parent side ------------------------------------------------------
def buildTasks(grid: dict, runs: int, baseSeed: int, seedMode: str):
    tasks = []
    linear = 0
    for i1, Pc in enumerate(grid["crossoverValues"]):
        for i2, Pm in enumerate(grid["mutationValues"]):
            for i3, sel in enumerate(grid["selectionFunctions"]):
                for i4, xo in enumerate(grid["crossoverFunctions"]):
                    for i5, mut in enumerate(grid["mutationFunctions"]):
                        for r in range(runs):
                            seed = (baseSeed + r if seedMode == "crn"
                                    else baseSeed + linear)
                            tasks.append(((i1, i2, i3, i4, i5), r, seed,
                                          Pc, Pm, sel, xo, mut))
                            linear += 1
    return tasks


def save(out_dir: str, stamp: str, fitnesses: np.ndarray,
         meta: dict, partial: bool) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = "_partial" if partial else ""
    base = os.path.join(out_dir, f"ga_param_search_parallel_{stamp}{tag}")
    data = {"fitnesses": fitnesses,
            "mean_fitnesses": np.nanmean(fitnesses, axis=5)}
    np.savez(base + ".npz", **data)
    written = [base + ".npz"]
    try:
        from scipy.io import savemat
        savemat(base + ".mat", data)
        written.append(base + ".mat")
    except ImportError:
        pass
    with open(base + "_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    written.append(base + "_meta.json")
    return written


def main():
    defaultWorkers = max(1, (os.cpu_count() or 2) // 2 - 1)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--objective", choices=["destination", "conventional"],
                    default="destination")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--pop", type=int, default=100)
    ap.add_argument("--gens", type=int, default=50)
    ap.add_argument("--workers", type=int, default=defaultWorkers,
                    help=f"default {defaultWorkers} = physical cores - 1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seed-mode", choices=["crn", "independent"],
                    default="crn")
    ap.add_argument("--initials", default=DEFAULT_XLSX)
    ap.add_argument("--out", default=DEFAULT_OUT)
    # Building & Car tab values (the GUI launcher passes these through)
    ap.add_argument("--velocity", type=float,
                    default=CAR_PARAMS["carVelocity"],
                    help="car velocity in m/s")
    ap.add_argument("--floor-height", type=float,
                    default=CAR_PARAMS["floorHeight"])
    ap.add_argument("--door-open", type=float,
                    default=CAR_PARAMS["doorOpeningTime"])
    ap.add_argument("--door-close", type=float,
                    default=CAR_PARAMS["doorClosingTime"])
    ap.add_argument("--transfer-time", type=float,
                    default=CAR_PARAMS["passengerTransferTime"])
    ap.add_argument("--capacity", type=int,
                    default=CAR_PARAMS["carCapacity"])
    ap.add_argument("--capacity-factor", type=float,
                    default=CAR_PARAMS["carCapacityFactor"])
    ap.add_argument("--smoke", action="store_true",
                    help="tiny grid/budget self-test (seconds, not hours)")
    args = ap.parse_args()

    from decision.meta.ga import GA
    grid = dict(GA.PARAM_SEARCH_GRID)
    if args.smoke:
        grid = SMOKE_GRID
        args.runs, args.pop, args.gens = 2, 20, 10
        args.workers = min(args.workers, 2)

    shape = (len(grid["crossoverValues"]), len(grid["mutationValues"]),
             len(grid["selectionFunctions"]),
             len(grid["crossoverFunctions"]),
             len(grid["mutationFunctions"]), args.runs)
    tasks = buildTasks(grid, args.runs, args.seed, args.seed_mode)
    total = len(tasks)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.smoke:
        stamp += "_smoke"

    carParams = dict(doorOpeningTime=args.door_open,
                     passengerTransferTime=args.transfer_time,
                     doorClosingTime=args.door_close,
                     carCapacity=args.capacity,
                     carCapacityFactor=args.capacity_factor,
                     carVelocity=args.velocity,
                     floorHeight=args.floor_height)

    print(f"parallel GA sweep: {int(np.prod(shape[:5]))} configurations "
          f"x {args.runs} runs = {total} tasks")
    print(f"  objective={args.objective}  pop={args.pop} "
          f"gens={args.gens}  seed-mode={args.seed_mode}")
    print(f"  cars: v={args.velocity:g} m/s, floors {args.floor_height:g} m"
          f" (inter-floor {args.floor_height / args.velocity:.2f} s),"
          f" doors {args.door_open:g}+{args.transfer_time:g}"
          f"+{args.door_close:g} s")
    print(f"  workers={args.workers} (below-normal priority)  "
          f"snapshot={os.path.basename(args.initials)}")

    fitnesses = np.full(shape, np.nan)
    meta = {"timestamp": stamp, "objective": args.objective,
            "snapshot": args.initials, "carParams": carParams,
            "populationSize": args.pop, "generations": args.gens,
            "runs": args.runs, "seedMode": args.seed_mode,
            "baseSeed": args.seed, "workers": args.workers,
            "grid": grid, "host": platform.node(),
            "cpu": platform.processor()}

    t0 = time.perf_counter()
    done = 0
    interrupted = False
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=args.workers, initializer=_initWorker,
                    initargs=(args.initials, args.objective,
                              args.pop, args.gens, carParams))
    try:
        every = max(1, total // 200)
        for idx, runIdx, cost in pool.imap_unordered(_runTask, tasks,
                                                     chunksize=1):
            fitnesses[idx + (runIdx,)] = cost
            done += 1
            if done % every == 0 or done == total:
                elapsed = time.perf_counter() - t0
                eta = elapsed / done * (total - done)
                print(f"  {done}/{total}  elapsed {elapsed / 60:6.1f} min"
                      f"  ETA {eta / 60:6.1f} min", flush=True)
        pool.close()
        pool.join()
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted - saving partial results "
              f"({done}/{total} tasks done, unfinished cells = NaN)")
        pool.terminate()
        pool.join()

    meta["tasksCompleted"] = done
    meta["elapsedSeconds"] = round(time.perf_counter() - t0, 1)
    written = save(args.out, stamp, fitnesses, meta, interrupted)
    print(f"\ndone in {meta['elapsedSeconds'] / 60:.1f} min; saved:")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
