"""ExactDispatcher: real objective, live-ID mapping, failure safety and engine E2E."""
from __future__ import annotations

import itertools
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision import Dispatcher, ExactDispatcher
from decision.exact_assignment import solve_exact_assignment
from decision.exact_dispatcher import ExactDispatchCancelled, ExactDispatchError
from decision.meta.obj_funs import objFunConventional1, objFunDestination
from data_structures import HallCall, HallCallLists, Passenger, PassengerLists


def options(**overrides):
    data = dict(stateUpdateTypeForNextDecision="fixed", exactMaxCalls=16,
                exactTimeLimitSeconds=10.0)
    data.update(overrides)
    return NS(**data)


def runtime():
    cars = [NS(id=17, floor=2.5, state=1, DF={6}, stopOverTime=2.0, velocityFps=0.5),
            NS(id=42, floor=6.0, state=-1, DF={2}, stopOverTime=3.1, velocityFps=4.0)]
    for car in cars:
        car.doorOpeningTime = 0.5 if car.id == 17 else 1.5
        car.capacity = 1  # never a constraint in the exact assignment objective
        car.load = 20
        car.updateServiceList = Mock()
        car.updateAboveBelowHCs = Mock()
        car.updateState = Mock()
    HC, P = HallCallLists(), PassengerLists()
    for floor, direction in ((2, 1), (5, 1), (2, 2), (7, 2)):
        HC.add(HallCall(floor, 0, direction))
    for floor, df in ((2, 6), (2, 5), (2, 7), (2, 8), (5, 8), (7, 1), (2, 1)):
        P.add(Passenger(floor, 0, df))
    # Assignment must use call keys even if caller lists are not sorted.
    HC.waiting[1].reverse()
    HC.waiting[2].reverse()
    return NS(nf=8), cars, HC, P


def assignment_ids(HC, P):
    return ([h.carId for d in (1, 2) for h in HC.waiting[d]],
            [p.carId for d in (1, 2) for p in P.waiting[d]])


class ExactDispatcherTests(unittest.TestCase):
    def test_real_dp_matches_exhaustive_objective_and_maps_real_ids(self):
        building, cars, HC, P = runtime()
        floors_before = [c.floor for c in cars]
        directions_before = [c.state for c in cars]
        calls_before = [list(HC.waiting[d]) for d in (1, 2)]
        dispatcher = ExactDispatcher(options())
        self.assertIsInstance(dispatcher, Dispatcher)
        dispatcher.dispatch(building, cars, HC, P)
        result = dispatcher.last_result
        self.assertEqual(result.status, "optimal")
        self.assertEqual(dispatcher.last_call_order,
                         [(2, "up"), (5, "up"), (2, "down"), (7, "down")])
        rows = np.array(list(itertools.product((1, 2), repeat=4)))
        costs = objFunDestination(cars, [2, 5, 2, 7], 2, rows, 8, P, "WT")
        self.assertAlmostEqual(result.optimum_mean, float(costs.min()), delta=1e-9)
        self.assertAlmostEqual(result.optimum_total / 7, result.optimum_mean, delta=1e-9)
        expected = {key: cars[label].id
                    for key, label in zip(dispatcher.last_call_order, result.assignment)}
        for direction, name in ((1, "up"), (2, "down")):
            for call in HC.waiting[direction]:
                self.assertEqual(call.carId, expected[(call.floor, name)])
            for passenger in P.waiting[direction]:
                self.assertEqual(passenger.carId, expected[(passenger.floor, name)])
        self.assertEqual([c.floor for c in cars], floors_before)
        self.assertEqual([c.state for c in cars], directions_before)
        self.assertEqual([list(HC.waiting[d]) for d in (1, 2)], calls_before)
        self.assertEqual([c.DF for c in cars], [{6}, {2}])
        self.assertEqual([c.capacity for c in cars], [1, 1])

    def test_inherited_run_updates_service_lists_and_states_once(self):
        building, cars, HC, P = runtime()
        dispatcher = ExactDispatcher(options())
        dispatcher.run(building, cars, HC, P)
        for car in cars:
            car.updateServiceList.assert_called_once_with(HC, P)
            car.updateAboveBelowHCs.assert_called_once_with()
            car.updateState.assert_called_once_with("fixed")

    def test_mean_is_over_passengers_not_calls(self):
        car = NS(id=81, floor=1, state=1, DF=set(), stopOverTime=2.0,
                 velocityFps=1.0, capacity=1, load=99, doorOpeningTime=1.0)
        HC, P = HallCallLists(), PassengerLists()
        HC.add(HallCall(3, 0, 1))
        for df in (4, 5, 7):
            P.add(Passenger(3, 0, df))
        dispatcher = ExactDispatcher(options())
        dispatcher.dispatch(NS(nf=8), [car], HC, P)
        self.assertEqual(dispatcher.last_result.optimum_total, 6)
        self.assertEqual(dispatcher.last_result.optimum_mean, 2)
        self.assertEqual([p.carId for p in P.waiting[1]], [81] * 3)

    def test_empty_calls_do_not_solve_or_report_a_zero_optimum(self):
        dispatcher = ExactDispatcher(options())
        with patch("decision.exact_dispatcher.solve_exact_assignment") as solve:
            dispatcher.dispatch(NS(nf=8), [], HallCallLists(), PassengerLists())
        solve.assert_not_called()
        self.assertEqual(dispatcher.last_status, "no_calls")
        self.assertIsNone(dispatcher.last_result)

    def test_limits_and_cancel_keep_all_previous_assignments(self):
        for overrides, cancel, expected in (
                (dict(exactMaxCalls=3), None, "call_limit"),
                (dict(exactTimeLimitSeconds=0), None, "time_limit"),
                ({}, lambda: True, "cancelled")):
            building, cars, HC, P = runtime()
            for d in (1, 2):
                for obj in HC.waiting[d] + P.waiting[d]:
                    obj.carId = 17
            before = assignment_ids(HC, P)
            dispatcher = ExactDispatcher(options(**overrides), should_cancel=cancel)
            with self.assertRaises(ExactDispatchError) as error:
                dispatcher.run(building, cars, HC, P)
            self.assertEqual(error.exception.result.status, expected)
            if expected == "cancelled":
                self.assertIsInstance(error.exception, ExactDispatchCancelled)
            self.assertEqual(assignment_ids(HC, P), before)
            for car in cars:
                car.updateServiceList.assert_not_called()
                car.updateState.assert_not_called()

    def test_cancel_during_each_phase(self):
        for phase in ("costs", "dp"):
            cancelled = [False]
            def progress(stage, *_):
                if stage == phase:
                    cancelled[0] = True
            building, cars, HC, P = runtime()
            dispatcher = ExactDispatcher(options(), progress=progress,
                                         should_cancel=lambda: cancelled[0])
            with self.assertRaises(ExactDispatchCancelled):
                dispatcher.dispatch(building, cars, HC, P)
            self.assertEqual(dispatcher.last_result.stage, phase)
            self.assertEqual(assignment_ids(HC, P), ([0] * 4, [0] * 7))

    def test_cancel_between_solve_and_application(self):
        building, cars, HC, P = runtime()
        cancelled = [False]
        def solve_then_cancel(instance, **_):
            result = solve_exact_assignment(instance)
            cancelled[0] = True
            return result
        dispatcher = ExactDispatcher(options(), should_cancel=lambda: cancelled[0])
        with patch("decision.exact_dispatcher.solve_exact_assignment", side_effect=solve_then_cancel):
            with self.assertRaises(ExactDispatchCancelled):
                dispatcher.dispatch(building, cars, HC, P)
        self.assertEqual(dispatcher.last_status, "cancelled")
        self.assertEqual(dispatcher.last_result.stage, "application")
        self.assertEqual(assignment_ids(HC, P), ([0] * 4, [0] * 7))

    def test_invalid_inputs_fail_before_any_assignment(self):
        def duplicate_call(cars, HC, P):
            HC.add(HallCall(2, 0, 1))
        def unmatched_passenger(cars, HC, P):
            P.add(Passenger(3, 0, 5))
        def duplicate_car_id(cars, HC, P):
            cars[1].id = cars[0].id
        def pending_boarding(cars, HC, P):
            cars[0].pendingBoard = [dict(p=P.waiting[1][0], dir=1)]
        for change in (duplicate_call, unmatched_passenger, duplicate_car_id, pending_boarding):
            building, cars, HC, P = runtime()
            change(cars, HC, P)
            before = assignment_ids(HC, P)
            dispatcher = ExactDispatcher(options())
            with patch("decision.exact_dispatcher.solve_exact_assignment") as solve:
                with self.assertRaises(ValueError):
                    dispatcher.dispatch(building, cars, HC, P)
                solve.assert_not_called()
            self.assertEqual(assignment_ids(HC, P), before)

    def test_rejects_unsupported_objective_or_limits(self):
        for changed in (dict(objectiveFunction="Conventional Information"),
                        dict(objFun=objFunConventional1),
                        dict(stateUpdateTypeForNextDecision="flexible"),
                        dict(exactMaxCalls=0), dict(exactTimeLimitSeconds=-1),
                        dict(exactTimeLimitSeconds=float("nan"))):
            with self.assertRaises(ValueError):
                ExactDispatcher(options(**changed))

    def test_custom_initials_experiment_end_to_end(self):
        import experiment as experiment_module
        from data_conf import recKey
        from experiment import Experiment
        from simulator import Simulator
        from test_ga_custom_initials_e2e import _write_initials_workbook, _experiment_start_data
        dispatcher = ExactDispatcher(options())
        original = (Simulator._speed, Simulator._displayTrafficFlow,
                    Simulator._displayTabularData, Simulator._endTime)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory(prefix="esra_exact_dispatch_e2e_") as tmp:
            path = os.path.join(tmp, "initials.xlsx")
            _write_initials_workbook(path)
            try:
                os.chdir(tmp)
                Simulator._speed = None
                Simulator.getSetDisplayTrafficFlow(False)
                Simulator.getSetDisplayTabularData(False)
                Simulator.getSetEndTime(0)
                experiment = Experiment()
                with patch.object(experiment_module.time, "sleep", return_value=None):
                    result = experiment.run(_experiment_start_data(path, dispatcher))
                record = result.RECnew[recKey(1, 1, 1, 1, 1)]
                self.assertEqual(dispatcher.last_status, "optimal")
                self.assertEqual(sum(len(record.P.served[d]) for d in (1, 2)), 2)
                self.assertTrue(all(not record.P.waiting[d] for d in (1, 2)))
                mapping = {(h.floor, h.direction): h.carId
                           for d in (1, 2) for h in record.HC.served[d]}
                for d in (1, 2):
                    for p in record.P.served[d]:
                        self.assertEqual(p.carId, mapping[(p.floor, p.direction)])
                    self.assertTrue(all(p.carId == 0 for p in result.initialP.waiting[d]))
                    self.assertTrue(all(h.carId == 0 for h in result.initialHC.waiting[d]))
                self.assertTrue(os.path.isfile(experiment.resultsFile))
                self.assertTrue(np.isfinite(experiment.Pawt).all())
                self.assertTrue(np.isfinite(experiment.HCawt).all())
            finally:
                os.chdir(cwd)
                (Simulator._speed, Simulator._displayTrafficFlow,
                 Simulator._displayTabularData, Simulator._endTime) = original


if __name__ == "__main__":
    unittest.main()
