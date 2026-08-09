"""
tests/test_ga.py
=================
Fixed-seed tests for decision/meta/ga.py + decision/meta/mutate.py
(ports of GA.m / gaMutateWrapper.m / mutate.m). Run:

    python tests/test_ga.py

Per the RNG policy: seeded Generators only, no global state [P12]/[P23].
"""
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from decision.meta import GA, mutate
from decision.meta.obj_funs import objFunConventional1
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists


def make_start_data(**overrides):
    base = dict(stateUpdateTypeForNextDecision="fixed",
                G=40, nPop=40, mutationFunction="uniform",
                parameterSearch=False, numberOfRuns=1, seed=0,
                Pc=0.8, Pm=0.1,
                crossoverFcn="crossoverscattered",
                selectionFcn="selectionstochunif")
    base.update(overrides)
    return NS(**base)


# ---------------------------------------------------------------------
# mutate.m port
# ---------------------------------------------------------------------
def test_mutate_operators():
    rng = np.random.default_rng(0)
    original = np.array([1, 2, 3, 4, 1, 2, 3, 4, 1])

    # value-copy [P24]: the caller's array is never touched
    out = mutate(original, "uniform", 1.0, 4, rng)
    assert np.array_equal(original, [1, 2, 3, 4, 1, 2, 3, 4, 1])
    assert out.min() >= 1 and out.max() <= 4

    # rate 0: nothing may change (methods that gate on rand < rate)
    for method in ("uniform", "block", "scramble", "swap", "frequency"):
        out = mutate(original, method, 0.0, 4, np.random.default_rng(1))
        assert np.array_equal(out, original), method

    # swap keeps the multiset and moves exactly two positions
    out = mutate(np.array([1, 2, 3, 4]), "swap", 1.0, 4,
                 np.random.default_rng(2))
    assert sorted(out) == [1, 2, 3, 4]
    assert int((out != [1, 2, 3, 4]).sum()) == 2

    # scramble keeps the multiset
    out = mutate(original, "scramble", 1.0, 4, np.random.default_rng(3))
    assert sorted(out) == sorted(original)

    # block rewrites a contiguous run, labels stay in range
    out = mutate(original, "block", 1.0, 4, np.random.default_rng(4))
    changed = np.flatnonzero(out != original)
    assert out.min() >= 1 and out.max() <= 4
    if changed.size:
        assert changed[-1] - changed[0] == changed.size - 1, "contiguous"

    # frequency stays in range
    out = mutate(np.array([1, 1, 1, 1, 2]), "frequency", 1.0, 3,
                 np.random.default_rng(5))
    assert out.min() >= 1 and out.max() <= 3

    # degenerate sizes return unchanged instead of crashing [P25]
    assert np.array_equal(mutate(np.array([2]), "swap", 1.0, 3,
                                 np.random.default_rng(6)), [2])
    assert np.array_equal(mutate(np.array([2]), "scramble", 1.0, 3,
                                 np.random.default_rng(6)), [2])

    try:
        mutate(original, "nope", 0.5, 4, rng)
    except ValueError as e:
        assert "nope" in str(e)
    else:
        raise AssertionError("unknown method must raise")
    print("PASS  mutate: all five operators, copy semantics, guards")


# ---------------------------------------------------------------------
# GA engine
# ---------------------------------------------------------------------
def _target_objective(target):
    """Vectorized hamming distance to a known best chromosome."""
    target = np.asarray(target)

    def obj(population):
        return (np.asarray(population) != target).sum(axis=1)
    return obj


def test_ga_finds_known_optimum():
    target = [1, 2, 3, 1, 2, 3]
    disp = GA(make_start_data(seed=1))
    disp.nVar, disp.maxLabel = len(target), 3
    best, cost = disp.optimize(_target_objective(target))
    assert cost == 0 and list(best) == target, (best, cost)
    print("PASS  GA finds the known optimum (hamming objective)")


def test_ga_all_selection_crossover_variants():
    target = [2, 1, 3, 3, 1]
    for sel in GA.PARAM_SEARCH_GRID["selectionFunctions"]:
        for xo in GA.PARAM_SEARCH_GRID["crossoverFunctions"]:
            disp = GA(make_start_data(seed=7, selectionFcn=sel,
                                      crossoverFcn=xo, G=30, nPop=30))
            disp.nVar, disp.maxLabel = len(target), 3
            best, cost = disp.optimize(_target_objective(target))
            assert cost == 0, (sel, xo, best, cost)
    print("PASS  every selection x crossover variant converges")


def test_ga_all_mutation_variants():
    target = [1, 3, 2, 2, 3, 1]
    for mut in GA.PARAM_SEARCH_GRID["mutationFunctions"]:
        disp = GA(make_start_data(seed=11, mutationFunction=mut,
                                  Pm=0.2, G=40, nPop=40))
        disp.nVar, disp.maxLabel = len(target), 3
        best, cost = disp.optimize(_target_objective(target))
        assert cost <= 1, (mut, best, cost)
    print("PASS  every mutation variant reaches (near-)optimum")


def test_ga_determinism():
    target = [1, 2, 3, 1]
    runs = []
    for _ in range(2):
        disp = GA(make_start_data(seed=42))
        disp.nVar, disp.maxLabel = len(target), 3
        runs.append(disp.optimize(_target_objective(target)))
    assert np.array_equal(runs[0][0], runs[1][0])
    assert runs[0][1] == runs[1][1]
    print("PASS  equal seeds give identical GA results [P12]")


def test_parameter_search_sweep():
    """[P29] grid machinery on a shrunken grid: fitnesses shape, mean
    over runs, the !!! last-configuration return quirk, and the [P36]
    auto-save."""
    import glob
    import shutil
    import tempfile
    target = [1, 2, 2, 1]
    tmp = tempfile.mkdtemp(prefix="esra_ga_sweep_")
    disp = GA(make_start_data(parameterSearch=True, numberOfRuns=2,
                              G=15, nPop=20, seed=3,
                              paramSearchSaveDir=tmp))
    disp.nVar, disp.maxLabel = len(target), 2
    disp.PARAM_SEARCH_GRID = {
        "crossoverValues": [0.5, 0.8],
        "mutationValues": [0.1],
        "selectionFunctions": ["selectiontournament"],
        "crossoverFunctions": ["crossoverscattered"],
        "mutationFunctions": ["uniform", "swap"],
    }
    best, cost = disp.optimize(_target_objective(target))
    assert disp.fitnesses.shape == (2, 1, 1, 1, 2, 2)
    assert disp.meanFitnesses.shape == (2, 1, 1, 1, 2)
    assert np.allclose(disp.meanFitnesses,
                       disp.fitnesses.mean(axis=5))
    # !!! the returned pair is the LAST configuration's result
    assert cost == disp.fitnesses[-1, -1, -1, -1, -1, -1]
    # [P36] auto-save: .npz always (+ .mat when scipy is installed)
    saved = sorted(glob.glob(os.path.join(tmp, "ga_param_search_*.npz")))
    assert len(saved) == 1, saved
    with np.load(saved[0]) as z:
        assert z["fitnesses"].shape == (2, 1, 1, 1, 2, 2)
        assert np.allclose(z["mean_fitnesses"], disp.meanFitnesses)
    shutil.rmtree(tmp)
    print("PASS  parameterSearch sweep: shapes, means, last-run return, "
          "auto-save [P36]")


# ---------------------------------------------------------------------
# end-to-end: GA + objFunConventional1 through dispatch()
# ---------------------------------------------------------------------
def test_ga_dispatch_with_conventional_objective():
    HallCall.reset_id()
    Passenger.reset_id()
    HC = HallCallLists()
    for floor, dir_ in ((5, 1), (2, 1), (9, 1), (7, 2), (3, 2)):
        HC.add(HallCall(floor, 0, dir_))
    P = PassengerLists()
    P.add(Passenger(2, 0, 8))
    P.add(Passenger(7, 0, 1))

    def car(cid, floor, state):
        return NS(id=cid, floor=float(floor), state=state, DF=set(),
                  velocity=1.0, velocityFps=1.0, stopOverTime=2.0,
                  stopOverCounter=0.0)

    cars = [car(1, 1, 0), car(2, 5, 0), car(3, 10, 0)]
    disp = GA(make_start_data(objFun=objFunConventional1,
                              G=20, nPop=30, seed=0))
    disp.dispatch(NS(nf=10), cars, HC, P)

    assigned = {hc.floor: hc.carId
                for hc in HC.waiting[1] + HC.waiting[2]}
    assert set(assigned) == {5, 2, 9, 7, 3}
    assert all(cid in (1, 2, 3) for cid in assigned.values()), assigned
    by_floor = {p.floor: p for p in P.waiting[1] + P.waiting[2]}
    assert by_floor[2].carId == assigned[2]
    assert by_floor[7].carId == assigned[7]
    # the live fleet is untouched by the objective's state writes [P14]
    assert [c.state for c in cars] == [0, 0, 0]
    print("PASS  GA + objFunConventional1 end-to-end dispatch")


if __name__ == "__main__":
    test_mutate_operators()
    test_ga_finds_known_optimum()
    test_ga_all_selection_crossover_variants()
    test_ga_all_mutation_variants()
    test_ga_determinism()
    test_parameter_search_sweep()
    test_ga_dispatch_with_conventional_objective()
    print("\nALL GA TESTS PASSED")
