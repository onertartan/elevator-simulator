"""Small exact-reference HC, persistence and failure-path regression tests."""
from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_conf import DataConf
from decision.exact_assignment import solve_exact_assignment, SUCCESS_ATOL
from make_scenarios import read_snapshot, validate, write_snapshot
from scenario_generation import (
    HC_DEFAULT_RESTARTS, HC_MAX_SWEEPS,
    DestinationInstance, ClimbResult, ScenarioGenerationCancelled,
    ExactReferenceUnavailable, batch_best_difficulty, climb, difficulty,
    evaluate_saved_scenario, generate_difficulty_scenario, metadata_reference_type,
    wilson_interval,
)
from scenario_fixture import write_small_reference


class ScenarioGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="esra_exact_scenario_")
        self.addCleanup(self.temp.cleanup)
        self.reference = os.path.join(self.temp.name, "reference.xlsx")
        self.output = os.path.join(self.temp.name, "generated.xlsx")
        self.meta_path = os.path.splitext(self.output)[0] + ".meta.json"
        write_small_reference(self.reference)
        self.snapshot = read_snapshot(self.reference)
        self.instance = DestinationInstance(self.snapshot, 7, 0.5)

    def generate(self, **overrides):
        args = dict(stop_over_time=7.0, velocity_fps=0.5, door_opening_time=2.0, tries=1,
                    screen_restarts=2, confirm_restarts=3, seed0=20260901)
        args.update(overrides)
        return generate_difficulty_scenario(self.reference, self.output, 0, 100, **args)

    def load_meta(self):
        return json.loads(Path(self.meta_path).read_text(encoding="utf-8"))

    def test_deterministic_hc_uses_exact_reference(self):
        exact = solve_exact_assignment(self.instance)
        first = difficulty(self.instance, 5, 17, reference=exact)
        second = difficulty(self.instance, 5, 17, reference=exact)
        self.assertEqual(first.values_seconds, second.values_seconds)
        self.assertEqual(first.success_count, second.success_count)
        self.assertEqual(first.reference_type, "exact_optimum")
        legacy = batch_best_difficulty(self.instance, 5, 17)
        self.assertEqual(first.values_seconds, legacy.values_seconds)
        self.assertEqual(legacy.reference_type, "batch_best")
        self.assertEqual(metadata_reference_type({"best_objective_seconds": 123}), "batch_best")
        self.assertEqual(first.rtol, 0)

    def test_default_restart_count_is_1000(self):
        self.assertEqual(HC_DEFAULT_RESTARTS, 1000)
        for function, argument in (
                (difficulty, "restarts"),
                (generate_difficulty_scenario, "confirm_restarts"),
                (evaluate_saved_scenario, "restarts")):
            self.assertEqual(inspect.signature(function).parameters[argument].default, 1000)
        # Exercise the real measurement loop without running a large HC batch.
        exact = solve_exact_assignment(self.instance)
        with patch("scenario_generation.climb",
                   return_value=ClimbResult(exact.optimum_mean, 1, "no_improvement")) as search:
            result = difficulty(self.instance, reference=exact)
        self.assertEqual(search.call_count, 1000)
        self.assertEqual((result.runs, result.success_count, result.success_percent),
                         (1000, 1000, 100.0))
        self.assertEqual(len(result.values_seconds), 1000)

    def test_default_sweep_limit_is_100_and_early_stop_is_preserved(self):
        self.assertEqual(HC_MAX_SWEEPS, 100)
        self.assertEqual(inspect.signature(climb).parameters["max_sweeps"].default, 100)
        # Synthetic decreasing scores force the iteration-limit path; this
        # tests the budget mechanism, not a physical elevator objective.
        instance = NS(n_calls=1, n_cars=2, cost=Mock(return_value=1000.0),
                      costs=Mock(side_effect=[np.array([999.0 - i, 1000.0])
                                              for i in range(100)]))
        result = climb(instance, np.random.default_rng(0), return_details=True)
        self.assertEqual((result.sweeps, result.stop_reason, result.value),
                         (100, "sweep_limit", 900.0))
        self.assertEqual(instance.costs.call_count, 100)
        # Real tiny instance still exits before the cap when it cannot improve.
        converged = climb(self.instance, np.random.default_rng(0), return_details=True)
        self.assertEqual(converged.stop_reason, "no_improvement")
        self.assertLess(converged.sweeps, 100)

    def test_zero_hits_below_optimum_and_absolute_not_relative_tolerance(self):
        exact = solve_exact_assignment(self.instance)
        runs = [ClimbResult(exact.optimum_mean + 1e-5, HC_MAX_SWEEPS, "sweep_limit")] * 2
        with patch("scenario_generation.climb", side_effect=runs):
            result = difficulty(self.instance, 2, reference=exact)
        self.assertEqual(result.success_count, 0)
        self.assertEqual(result.success_percent, 0)
        self.assertGreater(result.best_observed_seconds, exact.optimum_mean)
        self.assertEqual(result.stop_reasons, ("sweep_limit", "sweep_limit"))
        with patch("scenario_generation.climb",
                   return_value=ClimbResult(exact.optimum_mean - 2 * SUCCESS_ATOL, 1, "no_improvement")):
            with self.assertRaisesRegex(ValueError, "below the exact optimum"):
                difficulty(self.instance, 1, reference=exact)

    def test_zero_optimum_and_inclusive_tolerance(self):
        s = dict(n_floors=8, n_cars=1, car_floor=[3], car_state=[1],
                 car_df=[[]], up=[(3, 5)], dn=[])
        instance = DestinationInstance(s, 2, 1)
        exact = solve_exact_assignment(instance)
        values = [0.0, SUCCESS_ATOL, SUCCESS_ATOL * 1.01]
        with patch("scenario_generation.climb",
                   side_effect=[ClimbResult(v, 1, "no_improvement") for v in values]):
            result = difficulty(instance, 3, reference=exact)
        self.assertEqual(result.success_count, 2)
        self.assertIsNone(result.relative_gaps)

    def test_incomplete_or_stale_reference_is_refused(self):
        exact = solve_exact_assignment(self.instance, time_limit_seconds=0)
        with self.assertRaises(ExactReferenceUnavailable):
            difficulty(self.instance, 1, reference=exact)
        exact = solve_exact_assignment(self.instance)
        self.instance.cars[0].stopOverTime += 1
        with self.assertRaisesRegex(ValueError, "does not match"):
            difficulty(self.instance, 1, reference=exact)

    def test_wilson_and_hc_budget_stopping_reason(self):
        low, high = wilson_interval(10, 100)
        self.assertAlmostEqual(low, 5.522913709, places=6)
        self.assertAlmostEqual(high, 17.436566150, places=6)
        self.assertAlmostEqual(wilson_interval(0, 5)[0], 0)
        self.assertAlmostEqual(wilson_interval(5, 5)[1], 100)
        results = [climb(self.instance, np.random.default_rng(seed),
                         max_sweeps=1, return_details=True) for seed in range(5)]
        self.assertTrue(any(r.stop_reason == "sweep_limit" for r in results))
        self.assertTrue(all(r.sweeps == 1 for r in results))

    def test_generation_full_metadata_round_trip_and_simulator_loader(self):
        result = self.generate()
        generated = read_snapshot(self.output)
        self.assertEqual(validate(generated, self.snapshot), [])
        metadata = self.load_meta()
        self.assertEqual(metadata["reference_type"], "exact_optimum")
        self.assertEqual(metadata["exact_solver"]["status"], "optimal")
        self.assertEqual(metadata["difficulty_metric"], "hc_optimum_hit_rate")
        self.assertEqual(metadata["capacity_assumption"], "unlimited")
        self.assertEqual(metadata["n_calls"], 3)
        self.assertEqual(metadata["n_waiting_passengers"], 3)
        self.assertEqual(metadata["door_opening_time"], 2.0)
        self.assertEqual(metadata["objective"]["waiting_time_endpoint"], "pickup_door_opening_start")
        self.assertEqual(metadata["screening"]["reference_type"], "batch_best")
        self.assertEqual(metadata["screening"]["seed"], 11)
        self.assertEqual(metadata["selection"]["seed"], 12)
        self.assertEqual(metadata["holdout_plan"]["seed"], 13)
        self.assertEqual(metadata["selection_measurement"], "selection.success_percent")
        self.assertEqual(metadata["holdout_evaluations"], [])
        self.assertEqual(result.best_cost, min(metadata["selection"]["values_seconds"]))
        self.assertEqual(result.optimum_cost, metadata["exact_solver"]["optimum_mean"])
        instance = DestinationInstance(generated, 7, 0.5, door_opening_time=2.0)
        self.assertAlmostEqual(instance.cost(metadata["exact_solver"]["assignment"]),
                               result.optimum_cost, delta=1e-9)
        self.assertEqual(metadata["hc_protocol"]["success_rtol"], 0)
        self.assertEqual(metadata["hc_protocol"]["max_sweeps"], 100)
        self.assertEqual(metadata["hc_protocol"]["max_coordinate_visits"],
                         100 * metadata["n_calls"])
        self.assertEqual(metadata["hc_protocol"]["max_objective_evaluations"],
                         1 + 100 * metadata["n_calls"] * metadata["n_cars"])
        self.assertEqual(metadata["confirm_restarts"], 3)  # explicit override preserved
        self.assertEqual(metadata["target_success_band_percent"], [0, 100])
        self.assertIn("source_sha256", metadata["source"])
        config = DataConf(NS(
            dataType=3, fileName=self.output,
            doorOpeningTime=2.0, passengerTransferTime=3.0, doorClosingTime=2.0,
            carCapacity=1, carCapacityFactor=1.0, carVelocity=1.5, floorHeight=3.0))
        self.assertEqual(len(config.initialCars), 2)
        self.assertEqual(sum(len(config.initialP.waiting[d]) for d in (1, 2)), 3)

    def test_holdout_is_separate_never_changes_selection(self):
        self.generate()
        original = self.load_meta()
        holdout = evaluate_saved_scenario(self.output, restarts=4)
        final = self.load_meta()
        self.assertEqual(holdout.seed, 13)
        for key in ("selection", "target_success_band_percent", "measured_success_percent",
                    "exact_solver", "best_objective_seconds"):
            self.assertEqual(original[key], final[key])
        self.assertFalse(final["holdout_evaluations"][0]["used_for_selection"])
        for seed in (11, 12, 13):
            with self.assertRaises(ValueError):
                evaluate_saved_scenario(self.output, restarts=1, seed=seed)
        with open(self.output, "ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "workbook changed"):
            evaluate_saved_scenario(self.output, restarts=1, seed=14)

    def test_holdout_rejects_legacy_and_changed_semantics_or_physics(self):
        self.generate()
        original = self.load_meta()
        variants = [
            {**original, "reference_type": "batch_best"},
            {**original, "velocity_fps": 0.25},
            {**original, "door_opening_time": 3.0},
            {**original, "source": {"source_sha256": {"changed.py": "x"}}},
        ]
        for changed in variants:
            Path(self.meta_path).write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises((ValueError, ExactReferenceUnavailable)):
                evaluate_saved_scenario(self.output, restarts=1)

    def test_limit_cancel_and_bad_seed_do_not_publish_output(self):
        for kwargs, exc_type in (
                (dict(exact_max_calls=2), ExactReferenceUnavailable),
                (dict(exact_time_limit=0, screen_restarts=0), ExactReferenceUnavailable),
                (dict(should_cancel=lambda: True), ScenarioGenerationCancelled),
                (dict(selection_seed=11), ValueError)):
            with self.subTest(kwargs=kwargs), self.assertRaises(exc_type):
                self.generate(**kwargs)
            self.assertFalse(os.path.exists(self.output))
            self.assertFalse(os.path.exists(self.meta_path))
        flag = [False]
        def progress(_a, _b, stage, _score):
            if stage.startswith("Exact DP"):
                flag[0] = True
        with self.assertRaises(ScenarioGenerationCancelled):
            self.generate(progress=progress, should_cancel=lambda: flag[0], screen_restarts=0)
        self.assertFalse(os.path.exists(self.output))

    def test_metadata_failure_keeps_prior_outputs_and_cleans_staging(self):
        Path(self.output).write_bytes(b"prior workbook")
        Path(self.meta_path).write_bytes(b"prior metadata")
        with patch("scenario_generation.json.dump", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.generate(screen_restarts=0)
        self.assertEqual(Path(self.output).read_bytes(), b"prior workbook")
        self.assertEqual(Path(self.meta_path).read_bytes(), b"prior metadata")
        self.assertFalse(list(Path(self.temp.name).glob(".esra_*")))

    def test_second_replace_failure_rolls_back_both_new_and_existing_outputs(self):
        replace = os.replace
        def fail_metadata(source, target):
            if str(source).endswith(".json") and target == self.meta_path:
                raise OSError("metadata replace failed")
            return replace(source, target)
        for existing in (False, True):
            if existing:
                Path(self.output).write_bytes(b"prior workbook")
                Path(self.meta_path).write_bytes(b"prior metadata")
            with patch("scenario_generation.os.replace", side_effect=fail_metadata):
                with self.assertRaises(OSError):
                    self.generate(screen_restarts=0)
            if existing:
                self.assertEqual(Path(self.output).read_bytes(), b"prior workbook")
                self.assertEqual(Path(self.meta_path).read_bytes(), b"prior metadata")
            else:
                self.assertFalse(os.path.exists(self.output))
                self.assertFalse(os.path.exists(self.meta_path))
            self.assertFalse(list(Path(self.temp.name).glob(".esra_*")))

    def test_reader_preserves_empty_car_destinations(self):
        s = read_snapshot(self.reference)
        s["car_df"][0] = []
        write_snapshot(self.reference, self.output, s)
        self.assertEqual(read_snapshot(self.output)["car_df"], [[], [4]])


if __name__ == "__main__":
    unittest.main()
