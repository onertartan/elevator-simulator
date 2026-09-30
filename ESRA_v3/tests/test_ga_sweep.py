"""Custom-grid contract, partial statistics and real multiprocessing checks."""
import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import openpyxl

from ga_sweep_config import (CAR_PARAMS, GRID_KEYS, load_experiment, rate_range,
                             validate_experiment, validate_grid)
from analysis.run_parallel_sweep import buildTasks, save

ROOT = Path(__file__).resolve().parents[1]
GRID = {"crossoverValues": [0.5], "mutationValues": [0.01, 0.02, 0.03],
        "selectionFunctions": ["selectionroulette"],
        "crossoverFunctions": ["crossoverscattered"],
        "mutationFunctions": ["uniform", "frequency"]}


def spec(snapshot, output):
    return {"schemaVersion": 1, "snapshot": str(snapshot), "outputDir": str(output),
            "grid": copy.deepcopy(GRID), "objective": "destination",
            "populationSize": 8, "generations": 2, "runs": 2, "workers": 2,
            "baseSeed": 23, "seedMode": "crn", "carParams": dict(CAR_PARAMS)}


def must_reject(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("Invalid experiment was accepted")


def test_ranges_validation_and_seeds():
    assert rate_range(0.01, 0.03, 0.01) == [0.01, 0.02, 0.03]
    assert rate_range(0.3, 0.9, 0.1) == [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    assert rate_range(0, 0, 0.1) == [0.0]
    for args in ((0.01, 0.03, 0), (0.03, 0.01, 0.01), (0, 0.03, 0.02),
                 (-0.01, 0.1, 0.01), (0, float("nan"), 0.1)):
        must_reject(lambda: rate_range(*args))
    for key, invalid in (("mutationValues", []), ("mutationValues", [0.1, 0.1]),
                         ("mutationValues", [float("nan")]),
                         ("mutationValues", [True]),
                         ("selectionFunctions", ["typo"])):
        bad = copy.deepcopy(GRID)
        bad[key] = invalid
        must_reject(lambda: validate_grid(bad))
    for key, value in (("runs", 0), ("workers", 0), ("populationSize", 1),
                       ("generations", -1), ("seedMode", "typo")):
        bad = spec("x.xlsx", ".")
        bad[key] = value
        must_reject(lambda: validate_experiment(bad))
    crn = list(buildTasks(GRID, 2, 23, "crn"))
    assert len(crn) == 12
    assert [t[2] for t in crn] == [23, 24] * 6
    assert {t[4] for t in crn} == {0.01, 0.02, 0.03}
    assert [t[2] for t in buildTasks(GRID, 2, 23, "independent")] == list(range(23, 35))
    print("PASS  inclusive decimal grid, invalid input and CRN/independent seeds")


def test_partial_results_statistics():
    shape = tuple(len(GRID[key]) for key in GRID_KEYS) + (2,)
    values = np.full(shape, np.nan)
    values[0, 0, 0, 0, 0] = [2.0, 4.0]
    values[0, 0, 0, 0, 1] = [5.0, np.nan]
    with tempfile.TemporaryDirectory(prefix="esra_partial_") as tmp:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            paths = save(tmp, "test", values, {"grid": GRID}, True)
        csv_path = next(p for p in paths if p.endswith(".csv"))
        with open(csv_path, encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 6
        assert float(rows[0]["mean_objective_s"]) == 3.0
        assert np.isclose(float(rows[0]["std_objective_s"]), np.sqrt(2))
        assert rows[1]["runs_completed"] == "1" and rows[1]["std_objective_s"] == ""
        assert rows[2]["runs_completed"] == "0" and rows[2]["mean_objective_s"] == ""
    print("PASS  CSV partial-run counts, sample standard deviation and missing values")


def test_custom_grid_cli():
    with tempfile.TemporaryDirectory(prefix="esra_grid_") as tmp:
        directory = Path(tmp)
        snapshot = directory / "snapshot with spaces.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["header"] * 16)
        ws.append(["header"] * 16)
        ws.append([5, 30, 40, 30, 2, 1, "true", 1, 0, None, 2, 4, None, 4, 1, None])
        ws.append([None] * 7 + [5, 0, None] + [None] * 6)
        wb.save(snapshot)
        wb.close()
        request = spec(snapshot.name, "results with spaces")
        config = directory / "experiment.json"
        collected = []
        for workers in (1, 2):
            request["workers"] = workers
            config.write_text(json.dumps(request), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "analysis" / "run_parallel_sweep.py"),
                "--config", str(config)], cwd=ROOT, capture_output=True,
                text=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
            assert "6 configurations x 2 runs = 12 tasks" in result.stdout
            out = directory / request["outputDir"]
            meta_path = sorted(out.glob("*_meta.json"))[-1]
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            assert meta["grid"] == GRID and meta["tasksCompleted"] == 12
            assert meta["populationSize"] == 8 and meta["generations"] == 2
            assert meta["status"] == "complete"
            assert meta["waitingTimeEndpoint"] == "pickup_door_opening_start"
            assert Path(meta["snapshot"]).read_bytes() == snapshot.read_bytes()
            saved_spec = load_experiment(meta["experimentConfig"])
            assert saved_spec["grid"] == GRID
            npz_path = str(meta_path).replace("_meta.json", ".npz")
            with np.load(npz_path) as data:
                fitness = data["fitnesses"]
                assert fitness.shape == (1, 3, 1, 1, 2, 2)
                assert np.isfinite(fitness).all()
                np.testing.assert_allclose(data["mean_fitnesses"], fitness.mean(axis=5))
                collected.append(fitness.copy())
            with open(str(meta_path).replace("_meta.json", "_summary.csv"),
                      encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == 6 and all(row["runs_completed"] == "2" for row in rows)
            for row, idx in zip(rows, np.ndindex(fitness.shape[:5])):
                assert float(row["Pm"]) == GRID["mutationValues"][idx[1]]
                assert float(row["mean_objective_s"]) == fitness[idx].mean()
        np.testing.assert_array_equal(*collected)
        legacy = subprocess.run([
            sys.executable, str(ROOT / "analysis" / "run_parallel_sweep.py"),
            "--smoke", "--initials", str(snapshot), "--workers", "1",
            "--out", str(directory / "legacy")], cwd=ROOT,
            capture_output=True, text=True, timeout=60)
        assert legacy.returncode == 0, legacy.stdout + legacy.stderr
        assert "4 configurations x 2 runs = 8 tasks" in legacy.stdout
        # Malformed workbook must fail before spawning a pool.
        bad = directory / "bad.xlsx"
        bad.write_bytes(b"not an Excel workbook")
        request["snapshot"] = str(bad)
        config.write_text(json.dumps(request), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "analysis" / "run_parallel_sweep.py"),
                                 "--config", str(config)], capture_output=True, text=True, timeout=15)
        assert result.returncode != 0 and "Cannot load custom initials" in result.stderr
    print("PASS  custom JSON -> real process pool -> exact grid/results/CSV; worker-count reproducibility")


if __name__ == "__main__":
    test_ranges_validation_and_seeds()
    test_partial_results_statistics()
    test_custom_grid_cli()
    print("\nAll GA sweep tests passed.")
