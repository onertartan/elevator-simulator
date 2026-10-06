"""
decision/meta/metaheuristic_dispatcher.py
==========================================
Abstract base class for the metaheuristic dispatchers (Claude's port of
matlab_src/decision/meta/MetaheuristicDispatcher.m). GA / PSO / DE
subclass this and implement optimize().

Deviation notes (continuing the [P#] family):

  [P12] RNG: MATLAB used the global randi stream. Per the project RNG
       policy (PROJECT_STATUS section 6.2) the port takes a seeded
       numpy Generator: start_data.rng if present, else
       default_rng(start_data.seed) (seed may be absent -> unseeded).
       No global state; initializePopulation uses endpoint=True to
       reproduce randi's INCLUSIVE [1, maxLabel] bounds.
  [P13] objFun: in MATLAB startData.objFun is a function handle that
       the app's start callback assembled from the Objective Function
       dropdown; that objective .m is not in matlab_src yet. The port
       reads getattr(start_data, "objFun", None) and dispatch() raises
       RuntimeError if hall calls exist while no objective is set.
       Concrete objective functions arrive with the GA port.
       Expected signature (from the MATLAB wrapper):
       objFun(cars_copy, HC_all, HC_numofups, population, nf, P, "WT")
       -> per-row costs for the population.
  [P14] cars.copy(): MATLAB Copyable makes a SHALLOW copy of each car
       (handle-valued properties stay shared). The port deep-copies
       each car — the safe stand-in until the objective functions are
       ported and the sharing question can be settled against their .m
       source. As in MATLAB the copy happens INSIDE the wrapper, so
       every objective evaluation sees fresh copies.
  [P15] carId: the chromosome labels are 1..nc; MATLAB assigns the raw
       label as carId. The port maps label -> cars[label-1].id
       (identical results, ids are 1..N — same convention as the
       NearestCarDispatcher port).
  [P16] The MATLAB Abstract block declares
       optimize(dispatcher, FitnessFcn, numofHCs), but the actual call
       — and every subclass (GA.m / PSO.m / DE.m) — uses
       optimize(objFunWrapper) with one argument. MATLAB does not
       enforce abstract signatures; the Python ABC drops the vestigial
       numofHCs parameter.
  [P17] Alignment without sorting: MATLAB extracts registration-order
       floor arrays, sorts them ([HC_1,upindex]=sort(...)) and scatters
       the winning genes back through upindex
       (assignedCars(upindex)=assignedCars). In this port
       HallCallLists.add keeps each waiting list FLOOR-SORTED at
       insertion (bisect.insort — data_structures/hall_call_lists.py
       [P17]), so list position == MATLAB's sorted rank and gene i
       simply belongs to HC.waiting[dir][i]: both the sort and the
       unsort scatter disappear. Outcome-identical because (a) floor
       uniqueness per direction is guaranteed (simulator.py:204/235
       guards; the car.py:370 re-add happens after the old call left
       waiting via transfer), and (b) insort-right keeps registration
       order among equal floors, matching MATLAB's stable sort.
       dispatch() asserts the invariant as a tripwire.
       PassengerLists.add overrides back to plain append — passenger
       lists keep registration order (boarding slices P.waiting in
       list order).

MATLAB quirks preserved (flagged !!!):
  * bestSolution / bestCost are (re)initialized to zeros / inf on every
    dispatch but NEVER updated afterwards — optimize()'s results stay
    in locals, exactly as in MetaheuristicDispatcher.m line 60.
"""
from __future__ import annotations

import copy
import math
from abc import abstractmethod
from typing import Any, Callable, List, Optional, Sequence, Tuple

import numpy as np

from building import Building
from car import Car
from data_structures import PassengerLists, HallCallLists
from ..dispatcher import Dispatcher


class MetaheuristicDispatcher(Dispatcher):
    """Shared machinery for label-encoded metaheuristic dispatching:
    every hall call (sorted up-calls then sorted down-calls) is one gene
    whose value is the serving car's label 1..nc."""

    def __init__(self, start_data: Any):
        super().__init__(start_data)
        self.maxIter: int = start_data.G                  # max iterations
        self.nPop: int = start_data.nPop                  # population size
        self.objFun: Optional[Callable] = getattr( start_data, "objFun", None) # [P13]
        self.mutationFunction: str = start_data.mutationFunction
        self.parameterSearch: bool = start_data.parameterSearch
        self.numRunsForDispatcher: int = start_data.numberOfRuns
        rng = getattr(start_data, "rng", None)            # [P12]
        self.rng: np.random.Generator = (
            rng if rng is not None
            else np.random.default_rng(getattr(start_data, "seed", None)))

        self.population: Optional[np.ndarray] = None
        self.maxLabel: Optional[int] = None    # nc — highest car label
        self.nVar: Optional[int] = None        # number of hall calls
        self.bestSolution: Optional[np.ndarray] = None
        self.bestCost: Optional[float] = None

    # ------------------------------------------------------------------
    @abstractmethod
    def optimize(self, obj_fun_wrapper: Callable) -> Tuple[Sequence, float]:
        """Run the metaheuristic; return (best_chromosome, best_cost).
        [P16] single-argument form matching GA.m / PSO.m / DE.m."""

    # ------------------------------------------------------------------
    def initializePopulation(self) -> np.ndarray:
        """randi([1, maxLabel], nPop, nVar) — inclusive bounds. [P12]"""
        return self.rng.integers(1, self.maxLabel,
                                 size=(self.nPop, self.nVar),
                                 endpoint=True)

    # ------------------------------------------------------------------
    def dispatch(self, building: Building, cars: List[Car], HC: HallCallLists, P: PassengerLists,
                 traffic: Any = None) -> None:
        """Encode waiting hall calls as a chromosome (up calls then down
        calls, in floor order [P17]), optimize the car-label assignment,
        and write carIds back to the hall calls and their waiting
        passengers."""
        nf = building.nf                                # number of floors

        up, down = HC.waiting[1], HC.waiting[2]
        # [P17] tripwire: HallCallLists.add maintains floor order
        assert all(up[i].floor <= up[i + 1].floor
                   for i in range(len(up) - 1)), "up HC list not sorted"
        assert all(down[i].floor <= down[i + 1].floor
                   for i in range(len(down) - 1)), "down HC list not sorted"

        HC_1 = [hc.floor for hc in up]              # sorted up-call floors
        HC_2 = [hc.floor for hc in down]            # sorted down-call floors

        HC_all = HC_1 + HC_2
        HC_numofups = len(HC_1)
        numofHCs = len(HC_all)
        nc = len(cars)
        self.nVar = numofHCs
        self.maxLabel = nc

        if numofHCs == 0:
            return

        self.bestSolution = np.zeros(numofHCs)   # !!! never updated —
        self.bestCost = math.inf                 # !!! MATLAB quirk, see top

        if self.objFun is None:                  # [P13]
            raise RuntimeError(
                "MetaheuristicDispatcher: start_data.objFun is not set; "
                "objective functions are ported together with GA "
                "(see [P13]).")

        obj_fun = self.objFun

        def objFunWrapper(population):
            # fresh copies for every evaluation, as in MATLAB [P14]
            return obj_fun([copy.deepcopy(car) for car in cars],
                           HC_all, HC_numofups, population, nf, P, "WT")

        best_chrom, best_cost = self.optimize(objFunWrapper)
        best_chrom = [int(v) for v in np.asarray(best_chrom).ravel()]

        if HC_1:
            self._assignDirection(1, best_chrom[:HC_numofups], cars, HC, P)
        if HC_2:
            self._assignDirection(2, best_chrom[HC_numofups:], cars, HC, P)

    # ------------------------------------------------------------------
    def _assignDirection(self, dir_: int, labels: List[int],
                         cars: List[Any], HC: Any, P: Any) -> None:
        """[P17] positional alignment: gene i belongs to the i-th call
        of the floor-sorted waiting list — replaces MATLAB's
        `assignedCars(upindex)=assignedCars` scatter."""
        for label, hall_call in zip(labels, HC.waiting[dir_]):
            car_id = cars[label - 1].id                  # [P15]
            hall_call.carId = car_id
            for passenger in P.waiting[dir_]:
                if passenger.floor == hall_call.floor:
                    passenger.carId = car_id
