"""Shared experiment contract for the GA search dialog and CLI runner."""
from __future__ import annotations

import copy
import json
import math
import os
from decimal import Decimal, InvalidOperation

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(ROOT, "matlab_src", "results")
GRID_KEYS = ("crossoverValues", "mutationValues", "selectionFunctions",
             "crossoverFunctions", "mutationFunctions")
CAR_PARAMS = dict(doorOpeningTime=2.0, passengerTransferTime=3.0,
                  doorClosingTime=2.0, carCapacity=10,
                  carCapacityFactor=1.0, carVelocity=1.5, floorHeight=3.0)
OBJECTIVES = {"Destination Information": "destination",
              "Conventional Information": "conventional"}


def default_grid():
    from decision.meta.ga import GA
    return copy.deepcopy(GA.PARAM_SEARCH_GRID)


def default_workers():
    return max(1, (os.cpu_count() or 2) // 2 - 1)


def rate_range(start, stop, step):
    """Inclusive decimal range. Reject endpoints not reached by the step."""
    try:
        start, stop, step = (Decimal(str(v)) for v in (start, stop, step))
    except InvalidOperation as exc:
        raise ValueError("Start, end and step must be numbers.") from exc
    if not all(v.is_finite() for v in (start, stop, step)):
        raise ValueError("Start, end and step must be finite.")
    if not 0 <= start <= stop <= 1 or step <= 0:
        raise ValueError("Rates require 0 <= start <= end <= 1 and step > 0.")
    steps = (stop - start) / step
    if steps != steps.to_integral_value():
        raise ValueError("The end value must be reachable with the chosen step.")
    if steps > 10000:
        raise ValueError("Use at most 10,001 values per rate axis.")
    return [float(start + i * step) for i in range(int(steps) + 1)]


def validate_grid(grid):
    if not isinstance(grid, dict) or set(grid) != set(GRID_KEYS):
        raise ValueError("Grid must contain exactly the five GA factor lists.")
    supported = default_grid()
    result = {}
    for key in GRID_KEYS:
        values = grid[key]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{key}: select at least one value.")
        if key in GRID_KEYS[:2]:
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError(f"{key}: rates must be finite numbers in [0, 1].")
            values = [float(v) for v in values]
        elif any(not isinstance(v, str) or v not in supported[key]
                 for v in values):
            raise ValueError(f"{key}: unsupported GA operator.")
        if len(set(values)) != len(values):
            raise ValueError(f"{key}: duplicate values are not allowed.")
        result[key] = list(values)
    return result


def configuration_count(grid):
    return math.prod(len(grid[key]) for key in GRID_KEYS)


def _integer(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return value


def validate_experiment(spec, base_dir=None):
    """Return a normalized, JSON-safe spec with absolute file paths."""
    if not isinstance(spec, dict) or spec.get("schemaVersion") != 1:
        raise ValueError("Expected a schemaVersion=1 GA experiment definition.")
    required = {"schemaVersion", "snapshot", "outputDir", "objective", "grid",
                "populationSize", "generations", "runs", "workers",
                "baseSeed", "seedMode", "carParams"}
    if set(spec) != required:
        raise ValueError(f"Experiment fields mismatch: {set(spec) ^ required}")
    result = copy.deepcopy(spec)
    result["grid"] = validate_grid(spec["grid"])
    for key, minimum in (("populationSize", 2), ("generations", 1), ("runs", 1),
                         ("workers", 1), ("baseSeed", 0)):
        result[key] = _integer(spec[key], key, minimum)
    if spec["objective"] not in OBJECTIVES.values():
        raise ValueError("Objective must be destination or conventional.")
    if spec["seedMode"] not in ("crn", "independent"):
        raise ValueError("Seed mode must be crn or independent.")
    for key in ("snapshot", "outputDir"):
        path = spec[key]
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"{key}: a path is required.")
        result[key] = os.path.abspath(os.path.join(base_dir or os.curdir, path))
    if not result["snapshot"].lower().endswith(".xlsx"):
        raise ValueError("The custom-initials snapshot must be an .xlsx workbook.")
    params = spec["carParams"]
    if not isinstance(params, dict) or set(params) != set(CAR_PARAMS):
        raise ValueError("Incomplete car parameters.")
    for key, value in params.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError(f"{key} must be a finite non-negative number.")
    _integer(params["carCapacity"], "carCapacity", 1)
    if (params["floorHeight"] <= 0 or params["carVelocity"] <= 0
            or round(params["carVelocity"] / params["floorHeight"], 2) <= 0):
        raise ValueError("Car velocity in floors/s must be positive after rounding.")
    if not 0 < params["carCapacityFactor"] <= 1:
        raise ValueError("carCapacityFactor must be in (0, 1].")
    return result


def load_experiment(path):
    with open(path, encoding="utf-8-sig") as stream:
        return validate_experiment(json.load(stream), os.path.dirname(os.path.abspath(path)))
