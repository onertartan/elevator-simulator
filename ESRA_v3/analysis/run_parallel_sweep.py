"""
analysis/run_parallel_sweep.py
===============================
Parallel GA parameter-search runner for the shared workstation.

Runs a JSON experiment's grid, or GA.PARAM_SEARCH_GRID for legacy CLI
invocations (7 Pc x 5 Pm x 3 selection x 3 crossover x 5 mutation), as
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

Output (same tensor axis order as [P36]; arbitrary factor levels are
recorded in metadata and explicitly labelled in the CSV summary):
  matlab_src/results/ga_param_search_parallel_<stamp>.npz  (+ .mat)
      fitnesses       (Pc,Pm,selection,crossover,mutation,runs)
      mean_fitnesses  (Pc,Pm,selection,crossover,mutation)
  ..._meta.json       objective, budget, seeds, workers, elapsed, host
  ..._summary.csv     one row per configuration, completed-run statistics
  ..._experiment.json / ..._initials.xlsx  reproducible inputs
Ctrl+C saves whatever finished so far (unfinished cells = NaN,
filename suffixed _partial).

Usage (from the ESRA_v3/ root):
    .venv/Scripts/python analysis/run_parallel_sweep.py --config experiment.json
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
import csv
import ctypes
import datetime
import json
import hashlib
import multiprocessing as mp
import platform
import shutil
import sys
import time
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ga_sweep_config import (CAR_PARAMS, DEFAULT_OUT, GRID_KEYS, configuration_count,
                             default_grid, default_workers, load_experiment,
                             validate_experiment)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_XLSX = os.path.join(ROOT, "matlab_src", "initials_file.xlsx")

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
    linear = 0
    for i1, Pc in enumerate(grid["crossoverValues"]):
        for i2, Pm in enumerate(grid["mutationValues"]):
            for i3, sel in enumerate(grid["selectionFunctions"]):
                for i4, xo in enumerate(grid["crossoverFunctions"]):
                    for i5, mut in enumerate(grid["mutationFunctions"]):
                        for r in range(runs):
                            seed = (baseSeed + r if seedMode == "crn"
                                    else baseSeed + linear)
                            yield ((i1, i2, i3, i4, i5), r, seed,
                                   Pc, Pm, sel, xo, mut)
                            linear += 1


def save(out_dir: str, stamp: str, fitnesses: np.ndarray,
         meta: dict, partial: bool) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    tag = "_partial" if partial else ""
    base = os.path.join(out_dir, f"ga_param_search_parallel_{stamp}{tag}")
    counts = np.isfinite(fitnesses).sum(axis=5)
    means = np.divide(np.nansum(fitnesses, axis=5), counts,
                      out=np.full(counts.shape, np.nan), where=counts > 0)
    data = {"fitnesses": fitnesses, "mean_fitnesses": means}
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
    with open(base + "_summary.csv", "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Pc", "Pm", "selection", "crossover", "mutation",
                         "runs_requested", "runs_completed", "mean_objective_s",
                         "std_objective_s", "best_objective_s", "worst_objective_s"])
        for idx in np.ndindex(fitnesses.shape[:5]):
            values = fitnesses[idx]
            values = values[np.isfinite(values)]
            writer.writerow([meta["grid"][key][i] for key, i in zip(GRID_KEYS, idx)] + [
                fitnesses.shape[5], len(values),
                float(values.mean()) if len(values) else "",
                float(values.std(ddof=1)) if len(values) > 1 else "",
                float(values.min()) if len(values) else "",
                float(values.max()) if len(values) else ""])
    written.append(base + "_summary.csv")
    return written


def main():
    defaultWorkers = default_workers()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--config", help="complete JSON experiment; do not combine with other flags")
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

    try:
        if args.config:
            if any(a.startswith("--") and a.split("=")[0] != "--config"
                   for a in sys.argv[1:]):
                ap.error("--config cannot be combined with CLI experiment overrides.")
            spec = load_experiment(args.config)
        else:
            if args.smoke:
                args.runs, args.pop, args.gens = 2, 20, 10
                args.workers = min(args.workers, 2)
            spec = validate_experiment({
                "schemaVersion": 1, "grid": SMOKE_GRID if args.smoke else default_grid(),
                "snapshot": args.initials, "outputDir": args.out,
                "objective": args.objective, "populationSize": args.pop,
                "generations": args.gens, "runs": args.runs, "workers": args.workers,
                "baseSeed": args.seed, "seedMode": args.seed_mode,
                "carParams": dict(doorOpeningTime=args.door_open,
                                  passengerTransferTime=args.transfer_time,
                                  doorClosingTime=args.door_close,
                                  carCapacity=args.capacity,
                                  carCapacityFactor=args.capacity_factor,
                                  carVelocity=args.velocity, floorHeight=args.floor_height),
            })
        if not os.path.isfile(spec["snapshot"]):
            raise ValueError(f"Snapshot not found: {spec['snapshot']}")
    except (ValueError, OSError) as exc:
        ap.error(str(exc))

    grid, carParams = spec["grid"], spec["carParams"]
    shape = tuple(len(grid[key]) for key in GRID_KEYS) + (spec["runs"],)
    total = configuration_count(grid) * spec["runs"]
    tasks = buildTasks(grid, spec["runs"], spec["baseSeed"], spec["seedMode"])
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if args.smoke:
        stamp += "_smoke"

    # Preserve the actual workbook so reruns do not depend on later edits to
    # the source. Preflight in the parent avoids a respawning initializer loop
    # when a workbook is malformed.
    os.makedirs(spec["outputDir"], exist_ok=True)
    base = os.path.join(spec["outputDir"], f"ga_param_search_parallel_{stamp}")
    source_snapshot = spec["snapshot"]
    spec["snapshot"] = base + "_initials.xlsx"
    shutil.copyfile(source_snapshot, spec["snapshot"])
    try:
        from data_conf import DataConf
        dc = DataConf(NS(dataType=3, fileName=spec["snapshot"], **carParams))
        if not any(dc.initialHC.waiting.values()) or not dc.initialCars:
            raise ValueError("The snapshot needs at least one hall call and one car.")
    except Exception as exc:
        ap.error(f"Cannot load custom initials: {exc}")
    experiment_path = base + "_experiment.json"
    with open(experiment_path, "w", encoding="utf-8") as stream:
        json.dump(spec, stream, indent=2, ensure_ascii=False, allow_nan=False)
    with open(spec["snapshot"], "rb") as stream:
        snapshot_hash = hashlib.sha256(stream.read()).hexdigest()

    print(f"parallel GA sweep: {configuration_count(grid)} configurations "
          f"x {spec['runs']} runs = {total} tasks")
    print(f"  objective={spec['objective']}  pop={spec['populationSize']} "
          f"gens={spec['generations']}  seed-mode={spec['seedMode']}")
    print(f"  workers={spec['workers']} (below-normal priority)  "
          f"snapshot={os.path.basename(source_snapshot)}")

    fitnesses = np.full(shape, np.nan)
    meta = {"timestamp": stamp, "objective": spec["objective"],
            "waitingTimeEndpoint": "pickup_door_opening_start",
            "snapshot": spec["snapshot"], "sourceSnapshot": source_snapshot,
            "snapshotSHA256": snapshot_hash, "experimentConfig": experiment_path,
            "carParams": carParams, "populationSize": spec["populationSize"],
            "generations": spec["generations"], "runs": spec["runs"],
            "seedMode": spec["seedMode"], "baseSeed": spec["baseSeed"],
            "workers": spec["workers"], "grid": grid, "host": platform.node(),
            "cpu": platform.processor(), "tasksRequested": total,
            "workersUsed": min(spec["workers"], total)}

    t0 = time.perf_counter()
    done = 0
    interrupted = False
    error = None
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=min(spec["workers"], total), initializer=_initWorker,
                    initargs=(spec["snapshot"], spec["objective"],
                              spec["populationSize"], spec["generations"], carParams))
    try:
        every = max(1, total // 200)
        for idx, runIdx, cost in pool.imap_unordered(_runTask, tasks,
                                                     chunksize=1):
            if not np.isfinite(cost):
                raise ValueError("GA returned a non-finite objective value.")
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
    except Exception as exc:
        error = str(exc)
        pool.terminate()
        pool.join()

    meta["tasksCompleted"] = done
    meta["elapsedSeconds"] = round(time.perf_counter() - t0, 1)
    meta["status"] = "failed" if error else "interrupted" if interrupted else "complete"
    if error:
        meta["error"] = error
    written = save(spec["outputDir"], stamp, fitnesses, meta, interrupted or error is not None)
    print(f"\ndone in {meta['elapsedSeconds'] / 60:.1f} min; saved:")
    for path in written:
        print(f"  {path}")
    if error:
        print(f"Search failed: {error}", file=sys.stderr)
        return 1
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
