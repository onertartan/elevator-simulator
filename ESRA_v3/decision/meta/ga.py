"""
decision/meta/ga.py
====================
Port of matlab_src/decision/meta/GA.m (+ gaMutateWrapper.m) - the
genetic-algorithm dispatcher.

MATLAB delegates the actual optimization to the Global Optimization
Toolbox built-in ga(); that engine does not exist in Python, so
optimize() implements the documented ga() generational pipeline with
the options GA.m configured:

    rank fitness scaling        (ga default 'fitscalingrank')
    elitism                     (ga default EliteCount = ceil(0.05*nPop))
    CrossoverFraction split     nXover = round(Pc*(nPop-elite)), rest mutate
    SelectionFcn                selectionstochunif | selectionroulette |
                                selectiontournament (default size 4)
    CrossoverFcn                crossoverscattered | crossoversinglepoint |
                                crossovertwopoint
    MutationFcn                 the mutate.m port (decision/meta/mutate.py),
                                called directly - gaMutateWrapper.m existed
                                only to adapt MATLAB's MutationFcn signature
    Vectorized "on"             the whole population goes to objFunWrapper
                                in one call per generation

Deviation notes (continuing the [P#] family):

  [P26] Engine: results are statistically equivalent to MATLAB ga()
       but not RNG-identical (different generator and stream layout).
       All randomness comes from the dispatcher's seeded Generator
       [P12]. After selection the parent list is shuffled (as MATLAB's
       stepGA does) before the crossover/mutation split.
  [P27] GA.m declares a selectionFcn property but NEVER assigns it, so
       MATLAB silently runs the ga() default ('selectionstochunif')
       whatever the GUI chose. The Python GUI sends
       startData.selectionFcn (gui/tabs/control_method.py) and this
       port honours it, falling back to 'selectionstochunif' when
       absent.
  [P28] Stopping: exactly maxIter (MaxGenerations) generations. The
       ga() stall criteria (MaxStallGenerations/FunctionTolerance) are
       not replicated.
  [P29] parameterSearch: gaOutputFcn1's assignin('base', ...) exports
       become attributes: self.fitnesses (6-D, last axis = runs) and
       self.meanFitnesses (mean over runs), set once after the sweep.
       The per-configuration progress fprintf becomes a print at the
       start of each configuration. The sweep grids live in
       GA.PARAM_SEARCH_GRID so tests can shrink them.
  [P30] MATLAB round() rounds half AWAY from zero; Python's round()
       is banker's. nXover uses floor(x + 0.5) to match MATLAB.
  [P31] gaMethod is not sent by the Python GUI; read with default 1
       (GA.m line 5 property default).
  [P36] Auto-save (deviation): after a parameterSearch sweep the
       tensors are ALSO written to disk as
       ga_param_search_<timestamp>.npz (numpy, always) and .mat
       (when scipy is available), under startData.paramSearchSaveDir
       (default matlab_src/results/; set None to disable). MATLAB
       stopped at the assignin('base', ...) - closing MATLAB without
       a manual save() lost the whole sweep. A failed save never
       raises: the tensors always remain on the dispatcher.

MATLAB quirks preserved (flagged !!!):
  * !!! In parameterSearch mode every configuration overwrites
    (bestSolution, bestCost); the values RETURNED are those of the
    LAST grid configuration, not the best one - exactly like the
    ga() call inside GA.m's six nested loops.
"""
from __future__ import annotations

import datetime
import math
import os
from typing import Any, Callable, List, Sequence, Tuple

import numpy as np

from .metaheuristic_dispatcher import MetaheuristicDispatcher
from .mutate import mutate

# [P36] default target for the parameterSearch auto-save
_DEFAULT_SAVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))),
    "matlab_src", "results")


class GA(MetaheuristicDispatcher):
    """Label-encoded genetic algorithm dispatcher (port of GA.m)."""

    # [P29] GA.m optimize() lines 27-31 - the parameterSearch sweep grid
    PARAM_SEARCH_GRID = {
        "crossoverValues": [0.3, 0.4, 0.5, 0.6, 0.7, 0.8,0.9],
        "mutationValues": [0.01, 0.02, 0.05, 0.1, 0.2],
        "selectionFunctions": ["selectionstochunif", "selectionroulette",
                               "selectiontournament"],
        "crossoverFunctions": ["crossoverscattered", "crossoversinglepoint",
                               "crossovertwopoint"],
        "mutationFunctions": ["uniform", "block", "scramble", "swap",
                              "frequency"],
    }
    TOURNAMENT_SIZE = 4          # MATLAB selectiontournament default

    def __init__(self, start_data: Any):
        super().__init__(start_data)
        self.crossoverRate: float = start_data.Pc
        self.mutationRate: float = start_data.Pm
        self.gaMethod: int = getattr(start_data, "gaMethod", 1)      # [P31]
        self.crossoverFcn: str = start_data.crossoverFcn
        self.selectionFcn: str = getattr(start_data, "selectionFcn",
                                         "selectionstochunif")       # [P27]
        self.fitnesses: np.ndarray | None = None                     # [P29]
        self.meanFitnesses: np.ndarray | None = None
        self.paramSearchSaveDir: Any = getattr(
            start_data, "paramSearchSaveDir", _DEFAULT_SAVE_DIR)     # [P36]

    # ------------------------------------------------------------------
    def optimize(self, objFunWrapper: Callable) -> Tuple[np.ndarray, float]:
        """Run the GA; in parameterSearch mode sweep the [P29] grid the
        way GA.m's six nested loops do."""
        if self.parameterSearch:
            grid = self.PARAM_SEARCH_GRID
            crossoverValues = grid["crossoverValues"]
            mutationValues = grid["mutationValues"]
            selectionFunctions = grid["selectionFunctions"]
            crossoverFunctions = grid["crossoverFunctions"]
            mutationFunctions = grid["mutationFunctions"]
            numRuns = self.numRunsForDispatcher
        else:
            crossoverValues = [self.crossoverRate]
            mutationValues = [self.mutationRate]
            selectionFunctions = [self.selectionFcn]
            crossoverFunctions = [self.crossoverFcn]
            mutationFunctions = [self.mutationFunction]
            numRuns = 1

        shape = (len(crossoverValues), len(mutationValues),
                 len(selectionFunctions), len(crossoverFunctions),
                 len(mutationFunctions), numRuns)
        fitnesses = np.zeros(shape)
        totalConfigurations = int(np.prod(shape))
        totalCounter = 0

        bestSolution: np.ndarray = np.zeros(self.nVar, dtype=int)
        bestCost: float = math.inf

        for i1, Pc in enumerate(crossoverValues):
            for i2, Pm in enumerate(mutationValues):
                for i3, selFcn in enumerate(selectionFunctions):
                    for i4, xoverFcn in enumerate(crossoverFunctions):
                        for i5, mutFcn in enumerate(mutationFunctions):
                            for i6 in range(numRuns):
                                if self.parameterSearch:     # [P29] progress
                                    print(
                                        "Running configuration: "
                                        f"Pc={i1 + 1}/{len(crossoverValues)}, "
                                        f"Pm={i2 + 1}/{len(mutationValues)}, "
                                        f"Selection_Func={i3 + 1}/{len(selectionFunctions)}, "
                                        f"Crossover_Func={i4 + 1}/{len(crossoverFunctions)}, "
                                        f"Mutation_Func={i5 + 1}/{len(mutationFunctions)}, "
                                        f"Run_Num={i6 + 1}/{numRuns}\n"
                                        f" counter/Total={totalCounter}/{totalConfigurations}")
                                # !!! every run overwrites - the LAST
                                # configuration's result is returned
                                bestSolution, bestCost = self._runGA(
                                    objFunWrapper, Pc, Pm, selFcn,
                                    xoverFcn, mutFcn)
                                fitnesses[i1, i2, i3, i4, i5, i6] = bestCost
                                totalCounter += 1

        if self.parameterSearch:                             # [P29]
            self.fitnesses = fitnesses
            self.meanFitnesses = fitnesses.mean(axis=5)
            self._saveParamSearch()                          # [P36]

        return bestSolution, bestCost

    # ------------------------------------------------------------------
    def _saveParamSearch(self) -> None:
        """[P36] Persist the sweep tensors right after the sweep -
        MATLAB only pushed them into the base workspace, so a forgotten
        manual save() lost the run. Writes .npz always and .mat when
        scipy is present; a save failure is reported, never raised."""
        if not self.paramSearchSaveDir:
            return
        try:
            os.makedirs(self.paramSearchSaveDir, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            base = os.path.join(self.paramSearchSaveDir,
                                f"ga_param_search_{stamp}")
            data = {"fitnesses": self.fitnesses,
                    "mean_fitnesses": self.meanFitnesses}
            np.savez(base + ".npz", **data)
            saved = [base + ".npz"]
            try:
                from scipy.io import savemat     # optional dependency
                savemat(base + ".mat", data)
                saved.append(base + ".mat")
            except ImportError:
                print("parameterSearch: scipy not installed - "
                      ".mat skipped (.npz saved)")
            print("parameterSearch results saved:")
            for path in saved:
                print(f"  {path}")
        except Exception as exc:      # never lose a finished sweep to I/O
            print(f"parameterSearch: auto-save FAILED ({exc}); tensors "
                  "remain on the dispatcher as "
                  ".fitnesses/.meanFitnesses")

    # ------------------------------------------------------------------
    def _runGA(self, objFunWrapper: Callable, crossoverRate: float,
               mutationRate: float, selectionFcn: str, crossoverFcn: str,
               mutationFunction: str) -> Tuple[np.ndarray, float]:
        """One ga() run: the classic generational pipeline [P26]."""
        rng = self.rng
        nPop, nVar = self.nPop, self.nVar

        population = self.initializePopulation()
        costs = np.asarray(objFunWrapper(population), dtype=float).ravel()
        best = int(np.argmin(costs))
        bestSolution, bestCost = population[best].copy(), float(costs[best])

        eliteCount = min(nPop, math.ceil(0.05 * nPop))
        nXover = int(math.floor(crossoverRate * (nPop - eliteCount) + 0.5))  # [P30]
        nMutate = nPop - eliteCount - nXover
        nParents = 2 * nXover + nMutate

        for _ in range(self.maxIter):                        # [P28]
            order = np.argsort(costs, kind="stable")

            # rank scaling: expectation ~ 1/sqrt(rank), sum == nParents
            expectation = np.empty(nPop)
            expectation[order] = 1.0 / np.sqrt(np.arange(1, nPop + 1))
            expectation *= nParents / expectation.sum()

            parents = self._select(selectionFcn, expectation, nParents)
            rng.shuffle(parents)                             # [P26]

            elites = population[order[:eliteCount]]
            xoverKids = self._crossover(crossoverFcn, population,
                                        parents[:2 * nXover])
            mutateKids = np.array(
                [mutate(population[p], mutationFunction, mutationRate,
                        self.maxLabel, rng)
                 for p in parents[2 * nXover:]],
                dtype=int).reshape(nMutate, nVar)

            population = np.vstack([elites, xoverKids, mutateKids])
            costs = np.asarray(objFunWrapper(population), dtype=float).ravel()

            best = int(np.argmin(costs))
            if costs[best] < bestCost:
                bestSolution, bestCost = (population[best].copy(),
                                          float(costs[best]))

        return bestSolution, bestCost

    # ------------------------------------------------------------------
    def _select(self, name: str, expectation: np.ndarray,
                nParents: int) -> np.ndarray:
        """Indices of the selected parents (may repeat)."""
        rng = self.rng
        nPop = expectation.size

        if name == "selectionstochunif":
            # stochastic universal sampling: one spin, equally spaced
            # pointers (step 1 on a wheel of total length nParents)
            wheel = np.cumsum(expectation)
            stepSize = wheel[-1] / nParents
            position = rng.random() * stepSize
            parents = np.empty(nParents, dtype=int)
            lowest = 0
            for i in range(nParents):
                while wheel[lowest] < position:
                    lowest += 1
                parents[i] = lowest
                position += stepSize
            return parents

        if name == "selectionroulette":
            wheel = np.cumsum(expectation)
            picks = rng.random(nParents) * wheel[-1]
            return np.minimum(np.searchsorted(wheel, picks, side="left"),
                              nPop - 1)

        if name == "selectiontournament":
            candidates = rng.integers(0, nPop,
                                      size=(nParents, self.TOURNAMENT_SIZE))
            winner = expectation[candidates].argmax(axis=1)
            return candidates[np.arange(nParents), winner]

        raise ValueError(f"Unknown selection function: {name}")

    # ------------------------------------------------------------------
    def _crossover(self, name: str, population: np.ndarray,
                   parents: Sequence[int]) -> np.ndarray:
        """Consume the parent list pairwise, one child per pair
        (MATLAB crossover* semantics)."""
        rng = self.rng
        nVar = self.nVar
        nKids = len(parents) // 2
        kids = np.empty((nKids, nVar), dtype=int)

        for k in range(nKids):
            p1 = population[parents[2 * k]]
            p2 = population[parents[2 * k + 1]]

            if name == "crossoverscattered":
                child = p1.copy()
                mask = rng.random(nVar) > 0.5
                child[mask] = p2[mask]

            elif name == "crossoversinglepoint":
                cut = int(math.ceil((nVar - 1) * rng.random()))
                child = np.concatenate([p1[:cut], p2[cut:]])

            elif name == "crossovertwopoint":
                a = int(math.ceil((nVar - 1) * rng.random()))
                b = int(math.ceil((nVar - 1) * rng.random()))
                if a == b:                       # MATLAB wrap-around bump
                    b = a % max(1, nVar - 1) + 1
                if a > b:
                    a, b = b, a
                child = np.concatenate([p1[:a], p2[a:b], p1[b:]])

            else:
                raise ValueError(f"Unknown crossover function: {name}")

            kids[k] = child

        return kids
