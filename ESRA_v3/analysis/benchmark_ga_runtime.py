"""
analysis/benchmark_ga_runtime.py
=================================
Measure the Python GA's wall-clock cost per run on the realistic
custom-initials snapshot (matlab_src/initials_file.xlsx: 40 floors,
8 cars, 16 waiting hall calls) with the GUI-default GA budget
(nPop=100, 50 generations), then extrapolate to the full
parameterSearch sweep (1,350 configurations x 10 runs = 13,500 GA
executions) - the workload that takes days in MATLAB.

Usage (from the ESRA_v3/ root):
    .venv/Scripts/python analysis/benchmark_ga_runtime.py
"""
from __future__ import annotations

import copy
import os
import sys
import time
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from data_conf import DataConf
from decision.meta.ga import GA
from decision.meta.obj_funs import objFunConventional1, objFunDestination

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "matlab_src", "initials_file.xlsx")

SWEEP_RUNS = 6 * 5 * 3 * 3 * 5 * 10          # the full GA.m grid
N_TIMED = 3                                  # timed GA runs per objective


def main():
    # ---- the realistic dispatch snapshot ------------------------------
    sd = NS(dataType=3, fileName=XLSX,
            doorOpeningTime=2.0, passengerTransferTime=3.0,
            doorClosingTime=2.0, carCapacity=10, carCapacityFactor=1.0,
            carVelocity=1.5, floorHeight=3.0)
    dc = DataConf(sd)
    cars = dc.initialCars
    HC, P = dc.initialHC, dc.initialP
    nf = dc.BUILDING[0].nf

    HC_1 = [hc.floor for hc in HC.waiting[1]]
    HC_2 = [hc.floor for hc in HC.waiting[2]]
    HC_all = HC_1 + HC_2
    numofups = len(HC_1)
    print(f"snapshot: nf={nf}, cars={len(cars)}, "
          f"hall calls={len(HC_all)} ({numofups} up / {len(HC_2)} down)")

    for objName, objFun in (("objFunDestination", objFunDestination),
                            ("objFunConventional1", objFunConventional1)):

        def wrapper(population):
            # the [P14] dispatch wrapper: fresh deep copies per call
            return objFun([copy.deepcopy(c) for c in cars],
                          HC_all, numofups, population, nf, P, "WT")

        disp = GA(NS(stateUpdateTypeForNextDecision="fixed",
                     G=50, nPop=100, mutationFunction="uniform",
                     parameterSearch=False, numberOfRuns=1, seed=1,
                     Pc=0.8, Pm=0.05,
                     crossoverFcn="crossoverscattered",
                     selectionFcn="selectiontournament",
                     paramSearchSaveDir=None))
        disp.nVar, disp.maxLabel = len(HC_all), len(cars)

        # one objective call timed on its own (100-row population)
        pop = disp.initializePopulation()
        t0 = time.perf_counter()
        wrapper(pop)
        objMs = (time.perf_counter() - t0) * 1000

        disp.optimize(wrapper)                        # warm-up run
        times = []
        for k in range(N_TIMED):
            disp.rng = np.random.default_rng(100 + k)
            t0 = time.perf_counter()
            _, cost = disp.optimize(wrapper)
            times.append(time.perf_counter() - t0)
        perRun = float(np.mean(times))

        total = perRun * SWEEP_RUNS
        print(f"\n{objName}:")
        print(f"  one vectorized objective call (100 rows): {objMs:6.1f} ms")
        print(f"  one GA run (nPop=100, 50 generations):    {perRun:6.2f} s"
              f"   (best cost of last run: {cost:.3f})")
        print(f"  full sweep, {SWEEP_RUNS:,} runs, single core: "
              f"{total / 3600:5.1f} h")
        for workers in (4, 8, 16):
            print(f"    with {workers:>2} parallel workers:  "
                  f"~{total / 3600 / workers:5.1f} h")


if __name__ == "__main__":
    main()
