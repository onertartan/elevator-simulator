"""
tests/test_metaheuristic_dispatcher.py
=======================================
Fixed-seed unit tests for decision/meta/metaheuristic_dispatcher.py
(port of MetaheuristicDispatcher.m) and the [P17] floor-sorted
hall-call invariant it relies on. Run:

    python tests/test_metaheuristic_dispatcher.py

Covers, per the RNG policy in PROJECT_STATUS (seeded Generator, no
global state, operators verified with fixed seeds):
  * [P17] HallCallLists.add keeps waiting lists floor-sorted
    (insort-right: registration order among equal floors), transfer
    preserves the order, and PassengerLists.add stays a plain append.
  * initializePopulation: shape, INCLUSIVE randi bounds [1, maxLabel],
    determinism for equal seeds [P12].
  * dispatch plumbing with a stub optimize(): chromosome layout
    (up floors then down floors, both floor-sorted), POSITIONAL
    gene->call alignment [P17], carId mapping [P15], passenger
    co-assignment, and untouched other-floor passengers.
  * objFunWrapper contract [P13]/[P14]: argument order, fresh car
    copies per evaluation (mutations do not leak to the real cars).
  * numofHCs == 0 early return: optimize never called.
"""
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from decision import MetaheuristicDispatcher
from data_structures.hall_call import HallCall
from data_structures.hall_call_lists import HallCallLists
from data_structures.passenger import Passenger
from data_structures.passenger_lists import PassengerLists


def make_start_data(**overrides):
    base = dict(stateUpdateTypeForNextDecision="fixed",
                G=50, nPop=100, mutationFunction="uniform",
                parameterSearch=False, numberOfRuns=1, seed=0)
    base.update(overrides)
    return NS(**base)


class StubMeta(MetaheuristicDispatcher):
    """Records the wrapper and returns a preset chromosome."""

    def __init__(self, start_data, chromosome):
        super().__init__(start_data)
        self.chromosome = chromosome
        self.captured_wrapper = None
        self.optimize_calls = 0

    def optimize(self, obj_fun_wrapper):
        self.optimize_calls += 1
        self.captured_wrapper = obj_fun_wrapper
        return self.chromosome, 42.0


def mini_car(cid, floor=1):
    return NS(id=cid, floor=floor, state=0, stopOverCounter=0.0)


# ---------------------------------------------------------------------
# [P17] invariant on the data structures themselves
# ---------------------------------------------------------------------
def test_hall_call_lists_sorted_insertion():
    HallCall.reset_id()
    HC = HallCallLists()
    for floor, dir_ in ((5, 1), (2, 1), (9, 1), (7, 2), (3, 2)):
        HC.add(HallCall(floor, 0, dir_))
    assert [hc.floor for hc in HC.waiting[1]] == [2, 5, 9]
    assert [hc.floor for hc in HC.waiting[2]] == [3, 7]

    # transfer (removal) preserves order
    call_5 = next(hc for hc in HC.waiting[1] if hc.floor == 5)
    HC.transfer(call_5)
    assert [hc.floor for hc in HC.waiting[1]] == [2, 9]

    # insort-right: equal floors keep registration order (stable, like
    # MATLAB sort; the engine itself never creates same-floor duplicates)
    first = HallCall(4, 0, 1)
    second = HallCall(4, 1, 1)
    HC.add(first)
    HC.add(second)
    floor4 = [hc for hc in HC.waiting[1] if hc.floor == 4]
    assert [hc.id for hc in floor4] == [first.id, second.id]
    print("PASS  HallCallLists.add floor-sorted insertion [P17]")


def test_passenger_lists_keep_registration_order():
    Passenger.reset_id()
    P = PassengerLists()
    for floor, DF in ((5, 8), (2, 6), (9, 10)):
        P.add(Passenger(floor, 0, DF))
    # plain append — NOT floor-sorted (boarding order depends on this)
    assert [p.floor for p in P.waiting[1]] == [5, 2, 9]
    print("PASS  PassengerLists.add keeps registration order [P17]")


# ---------------------------------------------------------------------
# dispatcher machinery
# ---------------------------------------------------------------------
def test_initialize_population():
    disp = StubMeta(make_start_data(nPop=200, seed=0), [])
    disp.nVar = 7
    disp.maxLabel = 4
    pop = disp.initializePopulation()
    assert pop.shape == (200, 7)
    # inclusive randi bounds: both endpoints must be reachable and hit
    assert pop.min() == 1 and pop.max() == 4          # [P12]
    # determinism: same seed -> same population
    disp2 = StubMeta(make_start_data(nPop=200, seed=0), [])
    disp2.nVar, disp2.maxLabel = 7, 4
    assert np.array_equal(pop, disp2.initializePopulation())
    print("PASS  initializePopulation shape, inclusive bounds, fixed seed")


def _build_scenario():
    """Up calls registered at floors 5, 2, 9 and down calls at 7, 3
    (adds are floor-sorted by [P17]); three cars; passengers on some
    of those floors."""
    HallCall.reset_id()
    Passenger.reset_id()
    HC = HallCallLists()
    for floor, dir_ in ((5, 1), (2, 1), (9, 1), (7, 2), (3, 2)):
        HC.add(HallCall(floor, 0, dir_))
    P = PassengerLists()
    P.add(Passenger(2, 0, 8))     # up   @2 -> carId of call@2
    P.add(Passenger(7, 0, 1))     # down @7 -> carId of call@7
    P.add(Passenger(4, 0, 6))     # up   @4 -> no call, stays 0
    cars = [mini_car(1), mini_car(2), mini_car(3)]
    return HC, P, cars


def test_dispatch_positional_assignment():
    HC, P, cars = _build_scenario()
    # positional [P17]: genes for waiting[1] == [2,5,9] then
    # waiting[2] == [3,7]
    disp = StubMeta(make_start_data(objFun=lambda *a: [0.0]),
                    [3, 1, 2, 2, 3])
    disp.dispatch(NS(nf=10), cars, HC, P)

    assert disp.nVar == 5 and disp.maxLabel == 3
    assert {hc.floor: hc.carId for hc in HC.waiting[1]} == {2: 3, 5: 1, 9: 2}
    assert {hc.floor: hc.carId for hc in HC.waiting[2]} == {3: 2, 7: 3}
    # passengers co-assigned by floor+direction; unrelated one untouched
    by_floor = {p.floor: p for p in P.waiting[1] + P.waiting[2]}
    assert by_floor[2].carId == 3
    assert by_floor[7].carId == 3
    assert by_floor[4].carId == 0
    # MATLAB quirk: bestSolution/bestCost stay at their init values !!!
    assert list(disp.bestSolution) == [0.0] * 5
    assert disp.bestCost == float("inf")
    print("PASS  dispatch positional gene->call alignment [P17]")


def test_dispatch_tripwire_on_unsorted_list():
    HC, P, cars = _build_scenario()
    HC.waiting[1].reverse()               # simulate a broken invariant
    disp = StubMeta(make_start_data(objFun=lambda *a: [0.0]),
                    [1, 1, 1, 1, 1])
    try:
        disp.dispatch(NS(nf=10), cars, HC, P)
    except AssertionError:
        print("PASS  tripwire assert catches unsorted waiting list [P17]")
    else:
        raise AssertionError("expected the [P17] tripwire to fire")


def test_obj_fun_wrapper_contract():
    HC, P, cars = _build_scenario()
    seen = {}

    def obj_fun(cars_copy, HC_all, HC_numofups, population, nf, P_arg, kind):
        seen.update(cars_copy=cars_copy, HC_all=HC_all,
                    HC_numofups=HC_numofups, population=population,
                    nf=nf, P=P_arg, kind=kind)
        cars_copy[0].floor = 99          # must not leak [P14]
        return [0.0]

    disp = StubMeta(make_start_data(objFun=obj_fun), [1, 1, 1, 1, 1])
    disp.dispatch(NS(nf=10), cars, HC, P)
    disp.captured_wrapper("dummy-population")

    assert seen["HC_all"] == [2, 5, 9, 3, 7]      # sorted ups + sorted downs
    assert seen["HC_numofups"] == 3
    assert seen["nf"] == 10 and seen["kind"] == "WT"
    assert seen["population"] == "dummy-population"
    assert seen["P"] is P
    # fresh copies: mutation stayed in the copy, real car untouched
    assert seen["cars_copy"][0] is not cars[0]
    assert cars[0].floor == 1
    # second evaluation gets NEW copies (copy is inside the wrapper)
    disp.captured_wrapper("again")
    assert cars[0].floor == 1
    print("PASS  objFunWrapper argument contract and fresh car copies")


def test_no_hall_calls_early_return():
    HC, P = HallCallLists(), PassengerLists()
    cars = [mini_car(1), mini_car(2)]
    disp = StubMeta(make_start_data(), [])       # no objFun: must not raise
    disp.dispatch(NS(nf=10), cars, HC, P)
    assert disp.optimize_calls == 0
    assert disp.nVar == 0 and disp.maxLabel == 2
    print("PASS  empty hall-call lists: optimize not called")


def test_missing_obj_fun_raises():
    HC, P, cars = _build_scenario()
    disp = StubMeta(make_start_data(), [1, 1, 1, 1, 1])   # objFun absent
    try:
        disp.dispatch(NS(nf=10), cars, HC, P)
    except RuntimeError as e:
        assert "objFun" in str(e)
        print("PASS  missing objFun raises a clear RuntimeError [P13]")
    else:
        raise AssertionError("expected RuntimeError for missing objFun")


if __name__ == "__main__":
    test_hall_call_lists_sorted_insertion()
    test_passenger_lists_keep_registration_order()
    test_initialize_population()
    test_dispatch_positional_assignment()
    test_dispatch_tripwire_on_unsorted_list()
    test_obj_fun_wrapper_contract()
    test_no_hall_calls_early_return()
    test_missing_obj_fun_raises()
    print("ALL METAHEURISTIC-DISPATCHER TESTS PASSED")
