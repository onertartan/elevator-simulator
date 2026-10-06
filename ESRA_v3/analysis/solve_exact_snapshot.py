"""One bounded exact solve of an EXISTING, unchanged workbook (no resampling).

Example:
python analysis/solve_exact_snapshot.py --snapshot initials_files/initials_file.xlsx \
    --seconds 120 --max-calls 16 --stop-over 7 --door-open 2 --velocity-fps 0.5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.exact_assignment import DestinationInstance, OBJECTIVE_ID, solve_exact_assignment
from make_scenarios import read_snapshot
from scenario_generation import _source_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--max-calls", type=int, default=16)
    parser.add_argument("--stop-over", type=float, default=7.0)
    parser.add_argument("--door-open", type=float, default=2.0,
                        help="opening duration metadata; included in --stop-over, not added at pickup")
    parser.add_argument("--velocity-fps", type=float, default=0.5)
    parser.add_argument("--output", help="optional NEW JSON report path; never overwrites")
    args = parser.parse_args()
    if args.output and os.path.exists(args.output):
        parser.error("output exists; choose a new report filename")
    path = Path(args.snapshot).resolve()
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()
    instance = DestinationInstance(read_snapshot(path), args.stop_over, args.velocity_fps,
                                   door_opening_time=args.door_open)
    result = solve_exact_assignment(instance, max_calls=args.max_calls,
                                    time_limit_seconds=args.seconds)
    unchanged = digest_before == hashlib.sha256(path.read_bytes()).hexdigest()
    if not unchanged:
        raise RuntimeError("snapshot workbook changed during solve; result not saved")
    report = dict(snapshot=str(path), snapshot_file_sha256=digest_before,
                  snapshot_unchanged=unchanged, objective=OBJECTIVE_ID, mode="WT",
                  waiting_time_endpoint="pickup_door_opening_start",
                  capacity_assumption="unlimited", n_calls=instance.n_calls,
                  n_waiting_passengers=instance.n_passengers, n_cars=instance.n_cars,
                  stop_over_time=args.stop_over, velocity_fps=args.velocity_fps,
                  door_opening_time=args.door_open,
                  call_order=instance.call_order, source=_source_record(),
                  exact_solver=result.to_dict())
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        with open(args.output, "x", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print(text)
    return 0 if result.status == "optimal" else 2


if __name__ == "__main__":
    raise SystemExit(main())
