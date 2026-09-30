"""Difficulty-aware snapshots: HC hit rate against a COMPLETED exact DP.

Legacy batch-best rates remain explicitly named and may screen candidates.
Selection is measured against the exact optimum with a distinct seed stream;
a later holdout stream is never used to choose a candidate or adjust its band.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from decision.exact_assignment import (
    DestinationInstance, ExactAssignmentResult, OBJECTIVE_ID, SUCCESS_ATOL,
    content_hash, objective_source_hashes, solve_exact_assignment, _integer,
)
from make_scenarios import descriptors, draw, read_snapshot, validate, write_snapshot

HC_DEFAULT_RESTARTS = 1000
HC_MAX_SWEEPS = 100
HC_IMPROVEMENT_EPS = 1e-12


class ScenarioGenerationCancelled(RuntimeError):
    """A cancelled generation must not publish successful output."""


class ScenarioNotFound(RuntimeError):
    pass


class ExactReferenceUnavailable(RuntimeError):
    def __init__(self, result: ExactAssignmentResult):
        self.result = result
        super().__init__(
            f"Exact reference unavailable: {result.status} during {result.stage} "
            f"after {result.total_seconds:.3f} s "
            f"(costs {result.cost_precompute_seconds:.3f} s, DP {result.dp_seconds:.3f} s). "
            f"{result.message}. No scenario was saved.")


@dataclass(frozen=True)
class ClimbResult:
    value: float
    sweeps: int
    stop_reason: str


@dataclass(frozen=True)
class HCMeasurement:
    reference_type: str
    reference_value_seconds: float
    seed: int
    runs: int
    success_count: int
    success_percent: float
    wilson95_percent: tuple[float, float]
    best_observed_seconds: float
    values_seconds: tuple[float, ...]
    gaps_seconds: tuple[float, ...]
    relative_gaps: tuple[float, ...] | None
    sweeps: tuple[int, ...]
    stop_reasons: tuple[str, ...]
    elapsed_seconds: float
    atol_seconds: float = SUCCESS_ATOL
    rtol: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class GeneratedScenario:
    path: str
    metadata_path: str
    seed: int
    difficulty: float
    best_cost: float  # preserved meaning: best OBSERVED HC value, NOT DP optimum
    descriptors: dict
    optimum_cost: float
    selection: HCMeasurement
    reference_type: str = "exact_optimum"


def _cancel(should_cancel):
    if should_cancel and should_cancel():
        raise ScenarioGenerationCancelled("Scenario generation cancelled; no successful output")


def climb(instance: DestinationInstance, rng: np.random.Generator,
          max_sweeps: int = HC_MAX_SWEEPS,
          should_cancel: Optional[Callable[[], bool]] = None,
          *, return_details: bool = False):
    """Original random-start coordinate HC, with stopping reason recorded.

    np.argmin chooses the first (lowest car label) equal candidate. Acceptance
    still requires an improvement > 1e-12; reaching the sweep limit is NOT reported
    as convergence. Instrumentation/cancellation do not consume random draws.
    """
    _integer(max_sweeps, "max_sweeps", 1)
    _cancel(should_cancel)
    chromosome = rng.integers(0, instance.n_cars, size=instance.n_calls, dtype=int)
    current = instance.cost(chromosome)
    reason = "sweep_limit"
    for sweep in range(1, max_sweeps + 1):
        _cancel(should_cancel)
        improved = False
        for gene in rng.permutation(instance.n_calls):
            _cancel(should_cancel)
            old_label = int(chromosome[gene])
            candidates = np.repeat(chromosome.reshape(1, -1), instance.n_cars, axis=0)
            candidates[:, gene] = np.arange(instance.n_cars)
            values = instance.costs(candidates)
            best_label = int(np.argmin(values))
            best_value = float(values[best_label])
            if best_value < current - HC_IMPROVEMENT_EPS:
                chromosome[gene] = best_label
                current = best_value
                improved = True
            else:
                chromosome[gene] = old_label
        if not improved:
            reason = "no_improvement"
            break
    result = ClimbResult(current, sweep, reason)
    return result if return_details else current


def wilson_interval(successes: int, runs: int) -> tuple[float, float]:
    """Two-sided 95% Wilson interval, in PERCENT, for a fixed HC protocol."""
    _integer(runs, "runs", 1)
    _integer(successes, "successes")
    if successes > runs:
        raise ValueError("success count exceeds run count")
    z = 1.959963984540054
    p = successes / runs
    denominator = 1 + z * z / runs
    center = (p + z * z / (2 * runs)) / denominator
    half = z * math.sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs)) / denominator
    return (100 * max(0.0, center - half), 100 * min(1.0, center + half))


def _measure(instance, restarts, seed, reference_value, reference_type,
             should_cancel=None, progress=None):
    _integer(restarts, "restarts", 1)
    _integer(seed, "seed")
    started = time.perf_counter()
    rng = np.random.default_rng(seed)
    runs = []
    for index in range(restarts):
        _cancel(should_cancel)
        run = climb(instance, rng, should_cancel=should_cancel, return_details=True)
        if not math.isfinite(run.value) or run.value < 0:
            raise ValueError("HC returned a non-finite or negative objective")
        runs.append(run)
        if progress:
            progress(index + 1, restarts)
    values = np.array([r.value for r in runs])
    best = float(values.min())
    if reference_type == "batch_best":
        reference_value = best
    if reference_value is None or not math.isfinite(reference_value) or reference_value < 0:
        raise ValueError("invalid HC reference objective")
    if np.any(values < reference_value - SUCCESS_ATOL):
        raise ValueError("HC value is below the exact optimum: inconsistent problem or cost")
    # The legacy screen keeps its historical strict < rule; exact hits use <=.
    errors = np.abs(values - reference_value)
    hits = int(np.sum(errors < SUCCESS_ATOL if reference_type == "batch_best"
                      else errors <= SUCCESS_ATOL))
    gaps = values - reference_value  # never clip a negative discrepancy
    return HCMeasurement(
        reference_type, float(reference_value), seed, restarts, hits,
        100.0 * hits / restarts, wilson_interval(hits, restarts), best,
        tuple(map(float, values)), tuple(map(float, gaps)),
        tuple(map(float, gaps / reference_value)) if reference_value > 0 else None,
        tuple(r.sweeps for r in runs), tuple(r.stop_reason for r in runs),
        time.perf_counter() - started)


def batch_best_difficulty(instance: DestinationInstance, restarts: int = 150,
                          seed: int = 11, should_cancel=None, progress=None):
    """Legacy proxy ONLY: reaching the best value within this HC batch."""
    return _measure(instance, restarts, seed, None, "batch_best", should_cancel, progress)


def difficulty(instance: DestinationInstance, restarts: int = HC_DEFAULT_RESTARTS, seed: int = 12,
               should_cancel=None, *, reference: ExactAssignmentResult,
               progress=None) -> HCMeasurement:
    """HC optimum hit rate; no implicit fallback to a heuristic reference."""
    if reference.status != "optimal" or reference.optimum_mean is None:
        raise ExactReferenceUnavailable(reference)
    if reference.problem_fingerprint != instance.fingerprint():
        raise ValueError("exact reference does not match current snapshot/physics/Python objective")
    return _measure(instance, restarts, seed, reference.optimum_mean,
                    "exact_optimum", should_cancel, progress)


def metadata_reference_type(metadata: dict) -> str:
    """Old files without a reference tag are batch_best, never retroactively exact."""
    return metadata.get("reference_type", "batch_best")


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_record():
    root = Path(__file__).resolve().parent
    hashes = objective_source_hashes()
    for name in ("scenario_generation.py", "make_scenarios.py"):
        hashes[name] = _file_hash(root / name)
    options = dict(cwd=root, capture_output=True, text=True, timeout=5,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], **options)
        status = subprocess.run(["git", "status", "--porcelain"], **options)
        return dict(commit=commit.stdout.strip() if commit.returncode == 0 else None,
                    dirty=bool(status.stdout) if status.returncode == 0 else None,
                    source_sha256=hashes, numpy_version=np.__version__)
    except (OSError, subprocess.TimeoutExpired):
        return dict(commit=None, dirty=None, source_sha256=hashes, numpy_version=np.__version__)


def _hc_protocol(instance):
    return dict(
        algorithm="random_restart_coordinate_hill_climbing",
        initialization="independent uniform car label per floor-direction call",
        neighborhood="all car labels at one coordinate",
        coordinate_order="fresh random permutation each sweep",
        tie_breaking="numpy.argmin: first/lowest car label",
        acceptance="new_value < current_value - improvement_epsilon_seconds",
        improvement_epsilon_seconds=HC_IMPROVEMENT_EPS, max_sweeps=HC_MAX_SWEEPS,
        max_coordinate_visits=HC_MAX_SWEEPS * instance.n_calls,
        max_objective_evaluations=1 + HC_MAX_SWEEPS * instance.n_calls * instance.n_cars,
        stopping="no improvement in a full sweep OR sweep budget; recorded separately",
        rng="numpy.default_rng / PCG64", success_atol_seconds=SUCCESS_ATOL,
        success_rtol=0.0,
        interval_note="95% Wilson for fixed scenario/protocol; does not correct selection bias")


def generate_difficulty_scenario(
        reference_path: str, output_path: str, target_low: float, target_high: float,
        *, stop_over_time: float, velocity_fps: float, door_opening_time: float = 0.0,
        tries: int = 60, screen_restarts: int = 150,
        confirm_restarts: int = HC_DEFAULT_RESTARTS,
        seed0: int = 20260901, screen_seed: int = 11, selection_seed: int = 12,
        holdout_seed: int = 13, exact_max_calls: int = 16, exact_time_limit: float = 120.0,
        progress: Optional[Callable[[int, int, str, Optional[float]], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None) -> GeneratedScenario:
    """Generate -> optional batch-best screen -> DP -> exact-hit SELECTION.

    confirm_restarts is retained as an API name, but it is a selection-stage
    budget, not an independent holdout. A failed exact solve aborts this request
    with its status rather than spending the budget on more uncertified candidates.
    """
    reference_path, output_path = os.path.abspath(reference_path), os.path.abspath(output_path)
    if not os.path.isfile(reference_path):
        raise FileNotFoundError(reference_path)
    if (os.path.normcase(reference_path) == os.path.normcase(output_path)
            or os.path.exists(output_path) and os.path.samefile(reference_path, output_path)):
        raise ValueError("generated workbook must not overwrite its reference")
    if not output_path.lower().endswith(".xlsx"):
        raise ValueError("output must be an .xlsx workbook")
    if not 0 <= target_low <= target_high <= 100:
        raise ValueError("difficulty band must satisfy 0 <= low <= high <= 100")
    for value, name, minimum in ((tries, "tries", 1), (screen_restarts, "screen_restarts", 0),
                                 (confirm_restarts, "confirm_restarts", 1),
                                 (seed0, "seed0", 0), (screen_seed, "screen_seed", 0),
                                 (selection_seed, "selection_seed", 0),
                                 (holdout_seed, "holdout_seed", 0)):
        _integer(value, name, minimum)
    if len({screen_seed, selection_seed, holdout_seed}) != 3:
        raise ValueError("screening, selection and reserved holdout seeds must differ")
    _integer(exact_max_calls, "exact_max_calls")
    if not math.isfinite(exact_time_limit) or exact_time_limit < 0:
        raise ValueError("exact_time_limit must be finite and nonnegative")
    reference = read_snapshot(reference_path)
    # Input validation before any candidate work. Physics always come from
    # Building & Car, NEVER from the GUI dispatch/objective choice.
    base = DestinationInstance(reference, stop_over_time, velocity_fps,
                               door_opening_time=door_opening_time)
    if base.n_calls > exact_max_calls:
        raise ExactReferenceUnavailable(solve_exact_assignment(
            base, max_calls=exact_max_calls, time_limit_seconds=exact_time_limit,
            should_cancel=should_cancel))

    for attempt in range(1, tries + 1):
        _cancel(should_cancel)
        seed = seed0 + attempt - 1
        def report(stage, score=None):
            if progress:
                progress(attempt, tries, stage, score)
        report("Drawing candidate")
        candidate = draw(np.random.default_rng(seed), reference, reference["n_floors"],
                         should_cancel=lambda: _cancel(should_cancel))
        errors = validate(candidate, reference)
        if errors:
            continue
        instance = DestinationInstance(candidate, stop_over_time, velocity_fps,
                                       door_opening_time=door_opening_time)
        screening = None
        if screen_restarts:
            screening = batch_best_difficulty(
                instance, screen_restarts, screen_seed, should_cancel,
                lambda n, total: report(f"Batch-best screening HC {n}/{total}"))
            report("Batch-best screen (not optimum)", screening.success_percent)
            if not target_low - 8 <= screening.success_percent <= target_high + 8:
                continue
        exact = solve_exact_assignment(
            instance, max_calls=exact_max_calls, time_limit_seconds=exact_time_limit,
            should_cancel=should_cancel,
            progress=lambda stage, n, total: report(f"Exact DP {stage}: {n}/{total}"))
        if exact.status == "cancelled":
            raise ScenarioGenerationCancelled(exact.message)
        if exact.status != "optimal":
            raise ExactReferenceUnavailable(exact)
        selection = difficulty(
            instance, confirm_restarts, selection_seed, should_cancel, reference=exact,
            progress=lambda n, total: report(f"Exact-reference selection HC {n}/{total}"))
        report("HC optimum hit rate (selection)", selection.success_percent)
        if target_low <= selection.success_percent <= target_high:
            _cancel(should_cancel)
            return _write_result(
                reference_path, output_path, candidate, reference, instance, seed,
                selection, screening, exact, target_low, target_high, stop_over_time,
                velocity_fps, screen_seed, holdout_seed, should_cancel)
    raise ScenarioNotFound(
        f"No scenario met the {target_low:g}-{target_high:g}% HC optimum hit-rate band "
        f"after {tries} candidates. No output was saved.")


def _commit_outputs(pairs):
    """Stage both files first; restore prior outputs if either replacement fails.

    This handles ordinary I/O failures, not power-loss atomicity across files.
    Backups are retained with an explicit error if restoration itself fails.
    """
    backups, installed = {}, []
    rollback_failed = False
    try:
        for _, target in pairs:
            if os.path.exists(target):
                fd, backup = tempfile.mkstemp(prefix=".esra_backup_", dir=os.path.dirname(target))
                os.close(fd)
                backups[target] = backup
                shutil.copy2(target, backup)
        for staged, target in pairs:
            os.replace(staged, target)
            installed.append(target)
    except Exception as exc:
        for target in reversed(installed):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    os.remove(target)
            except OSError:
                rollback_failed = True
        if rollback_failed:
            raise RuntimeError(f"Output commit/rollback failed; inspect backups {backups}") from exc
        raise
    finally:
        for staged, _ in pairs:
            if os.path.exists(staged):
                os.remove(staged)
        if not rollback_failed:
            for backup in backups.values():
                if os.path.exists(backup):
                    os.remove(backup)


def _temporary_file(directory, suffix):
    fd, path = tempfile.mkstemp(prefix=".esra_scenario_", suffix=suffix, dir=directory)
    os.close(fd)
    return path


def _write_result(reference_path, output_path, candidate, reference, instance, seed,
                  selection, screening, exact, target_low, target_high,
                  stop_over_time, velocity_fps, screen_seed, holdout_seed, should_cancel):
    directory = os.path.dirname(output_path)
    os.makedirs(directory, exist_ok=True)
    metadata_path = os.path.splitext(output_path)[0] + ".meta.json"
    workbook_tmp = _temporary_file(directory, ".xlsx")
    metadata_tmp = None
    try:
        write_snapshot(reference_path, workbook_tmp, candidate)
        back = read_snapshot(workbook_tmp)
        if validate(back, reference) or content_hash(back) != content_hash(candidate):
            raise RuntimeError("generated workbook failed full snapshot round-trip check")
        metadata = dict(
            schema_version=2, objective=dict(id=OBJECTIVE_ID, mode="WT", units="seconds",
                                            waiting_time_endpoint="pickup_door_opening_start"),
            capacity_assumption="unlimited", call_grouping="floor_direction",
            n_calls=instance.n_calls, n_waiting_passengers=instance.n_passengers,
            n_cars=instance.n_cars, call_order=instance.call_order, assignment_index_base=0,
            reference_type="exact_optimum",
            difficulty_algorithm="random_restart_coordinate_hill_climbing",
            difficulty_metric="hc_optimum_hit_rate",
            direction="lower success percentage means harder",
            reference_file=reference_path, scenario_file=output_path, seed=seed,
            reference_file_sha256=_file_hash(reference_path),
            snapshot_sha256=content_hash(candidate), snapshot_file_sha256=_file_hash(workbook_tmp),
            source=_source_record(), exact_solver=exact.to_dict(),
            stop_over_time=stop_over_time, velocity_fps=velocity_fps,
            door_opening_time=instance.cars[0].doorOpeningTime,
            inter_floor_time_seconds=1.0 / velocity_fps, hc_protocol=_hc_protocol(instance),
            target_success_band_percent=[target_low, target_high],
            band_status="user target; not recalibrated against exact optima",
            selection_measurement="selection.success_percent",
            measured_success_percent=selection.success_percent,
            best_objective_seconds=selection.best_observed_seconds,
            best_objective_reference="selection_batch_best",
            optimum_objective_seconds=exact.optimum_mean,
            screening=screening.to_dict() if screening else None,
            screening_role="optional batch_best candidate filter, not an optimum or holdout estimate",
            screen_seed=screen_seed, screen_restarts=screening.runs if screening else 0,
            selection=selection.to_dict(), confirm_restarts=selection.runs,
            holdout_plan=dict(seed=holdout_seed, used_for_selection=False),
            holdout_evaluations=[], descriptors=descriptors(candidate))
        metadata_tmp = _temporary_file(directory, ".json")
        with open(metadata_tmp, "w", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2, allow_nan=False)
        _cancel(should_cancel)
        _commit_outputs([(workbook_tmp, output_path), (metadata_tmp, metadata_path)])
    finally:
        for path in (workbook_tmp, metadata_tmp):
            if path and os.path.exists(path):
                os.remove(path)
    return GeneratedScenario(
        output_path, metadata_path, seed, selection.success_percent,
        selection.best_observed_seconds, metadata["descriptors"], exact.optimum_mean, selection)


def evaluate_saved_scenario(workbook_path: str, *, restarts: int = HC_DEFAULT_RESTARTS,
                            seed: int | None = None, should_cancel=None,
                            progress=None) -> HCMeasurement:
    """Append a later holdout measurement; never reselect or change the band.

    Exact references may only be reused for the unchanged workbook, physics
    and Python source hashes. Legacy files require a NEW exact solve, not a
    metadata relabel. Reusing a selection/screen/previous holdout seed is refused.
    """
    workbook_path = os.path.abspath(workbook_path)
    metadata_path = os.path.splitext(workbook_path)[0] + ".meta.json"
    with open(metadata_path, encoding="utf-8") as stream:
        metadata = json.load(stream)
    if metadata_reference_type(metadata) != "exact_optimum":
        raise ValueError("legacy batch_best metadata is not an exact reference")
    if _file_hash(workbook_path) != metadata["snapshot_file_sha256"]:
        raise ValueError("snapshot workbook changed; recompute exact reference")
    snapshot = read_snapshot(workbook_path)
    if content_hash(snapshot) != metadata["snapshot_sha256"]:
        raise ValueError("snapshot content changed; recompute exact reference")
    if _source_record()["source_sha256"] != metadata["source"]["source_sha256"]:
        raise ValueError("Python semantics changed; recompute exact reference")
    seed = metadata["holdout_plan"]["seed"] if seed is None else seed
    used = {metadata["screen_seed"], metadata["selection"]["seed"]}
    used.update(item["seed"] for item in metadata.get("holdout_evaluations", []))
    if seed in used:
        raise ValueError("holdout requires an unused seed distinct from screening/selection")
    instance = DestinationInstance(snapshot, metadata["stop_over_time"], metadata["velocity_fps"],
                                   door_opening_time=metadata["door_opening_time"])
    exact = ExactAssignmentResult(**metadata["exact_solver"])
    if exact.status != "optimal" or exact.assignment is None:
        raise ExactReferenceUnavailable(exact)
    if not np.isclose(instance.cost(exact.assignment), exact.optimum_mean, atol=SUCCESS_ATOL, rtol=0):
        raise ValueError("saved optimum assignment failed direct objective recheck")
    measurement = difficulty(instance, restarts, seed, should_cancel,
                             reference=exact, progress=progress)
    record = measurement.to_dict()
    record["used_for_selection"] = False
    metadata["holdout_evaluations"].append(record)
    _cancel(should_cancel)
    temporary = _temporary_file(os.path.dirname(metadata_path), ".json")
    try:
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, metadata_path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return measurement
