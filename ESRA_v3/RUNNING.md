# Running the ESRA simulator (Python port)

Last updated: **2026-09-30**. The Destination/WT objective now compares both
initial service directions for `state=0` cars. This is a static cost change;
propagating the minimizing direction to the simulator is still pending.
See section 9 for the current contract and focused verification results.

## 1. One-time setup

    pip install -r requirements.txt        # PySide6, numpy, openpyxl, pyqtgraph
    pip install pandas                    # required for Excel result export; not in requirements.txt yet
    python tests/check_real_data_structures.py   # verifies YOUR data_structures package
    python tests/test_experiment_smoke.py        # engine suite (12 tests)

## 2. Run the app

    python main.py

Then in the window:
  * Building & Car tab ... pick floors/cars (small first: 8 floors, 3 cars)
  * Traffic tab .......... select "Passenger Arrival Rate", e.g. 4 s/passenger
  * Control Method tab ... "Nearest Car Method", or Metaheuristics/GA
                           (objective: Conventional/Destination Information)
                           or "Exact Dispatcher (Subset DP)" (see section 6)
  * Simulation Configuration tab ... duration e.g. 25; for New Traffic,
                                     initial passengers e.g. 2
  * Display tab .......... "Display traffic flow" on, Display speed 2-3
                           (5 = fastest; 1 = one frame per second)
  * Press Start - the window jumps to the Display tab and animates.
    Pause/Continue and Terminate work mid-run. "Save data" pickles the
    dataConf to a .pkl file. The current Recorded Traffic file dialog still
    advertises a .mat filter; it does not offer .pkl in its filter list.

## 3. GA parameter search

In **Control Method -> Metaheuristics -> GA**, click **Run GA Parameter
Search...**. Population size, maximum iterations (generations), and objective
are taken from the common Control Method controls and displayed read-only in
the dialog. Car physics parameters come from Building & Car Configuration.

The dialog lets you choose:

- A custom-initials `.xlsx` (the loaded/created file is preselected).
- `Pc` and `Pm` start/end/step ranges or explicit comma-separated value lists.
  Endpoints are inclusive; the step must reach the end exactly. For example,
  `0.01 .. 0.03` by `0.01` produces `[0.01, 0.02, 0.03]`.
- Multiple selection, crossover and mutation methods using checkboxes.
- Runs per configuration, base seed, CRN/independent seed mode, worker count,
  and output folder. The number of configurations and total runs updates live.

The normal toolbar **Start** always starts a simulation. Search settings are
saved separately with the UI state. Old `number_of_runs` settings migrate to
the new dialog; the old parameter-search checkbox no longer redirects Start.

Searches run in a separate console on Windows. Ctrl+C saves partial results;
closing the GUI does not stop a search. A search evaluates GA assignments on a
fixed snapshot, not the full dynamic simulation.

The chosen output folder contains:

- `ga_search_request_*.json`: the request saved by the GUI before launch.
- `ga_param_search_parallel_<stamp>_experiment.json`: resolved experiment,
  including the exact grid, budget, seeds, physics, and archived snapshot path.
- `..._initials.xlsx`: a copy of the workbook used for this run.
- `....npz`: `fitnesses` and `mean_fitnesses`; axes are
  `(Pc, Pm, selection, crossover, mutation, run)` and the same without `run`.
- `....mat`: the same tensors, if SciPy is installed.
- `..._meta.json`: exact axis values, completion status, timing and snapshot hash.
- `..._summary.csv`: one row per configuration, requested/completed counts,
  mean, sample standard deviation, best and worst objective values (seconds).
  Missing/unfinished observations are excluded; standard deviation is blank
  with fewer than two completed runs. Interrupted/error results use `_partial`.

Repeat an experiment with:

```powershell
.\.venv\Scripts\python.exe analysis\run_parallel_sweep.py --config "path\experiment.json"
```

Relative paths in JSON are resolved against the JSON file's folder. `--config`
is exclusive with other experiment flags. Existing CLI flags and `--smoke`
still work; without `--config` the default grid remains `GA.PARAM_SEARCH_GRID`.
Legacy analysis scripts that hard-code factor levels must not be used to label
custom grids; use the exported CSV/metadata (or a metadata-aware analysis).

Regression checks:

```powershell
.\.venv\Scripts\python.exe tests\test_gui_sweep_command.py
.\.venv\Scripts\python.exe tests\test_ga_sweep.py
```

## 4. Still MATLAB-only (pending upload/port)

  * ACO.m / PSO.m / DE.m  (GA + objFunConventional1/objFunDestination
    are ported; remaining objFuns: Number of Passengers, user-defined)
  * MDP path (dataType 3 'Load Custom Initials File' is now
    ported - configuration.py [F4]-[F7], matlab_src/utils originals)
  * (Dispatcher.m / DecisionMaker.m originals uploaded - decision/
    base classes CERTIFIED; findings in decision/decision_maker.py
    and decision/dispatcher.py docstrings.)

## 5. Exact-reference HC scenario difficulty

**Simulation Configuration -> Create Difficulty-Based Custom Initials...** now
selects scenarios by the percentage of random-start coordinate hill climbs
that reach a **completed subset-DP optimum**, not the best solution in the HC
batch. The fixed objective is the Python `objFunDestination(..., "WT")`:
estimated mean waiting time of waiting passengers. Subsequent Control Method
and Objective Function selections do not change this difficulty protocol.

The exact assignment model has unlimited capacity. A bit/gene represents one
floor-direction hall call, keeping all passengers behind that call together
and preserving their individual destinations. The denominator is the waiting
passenger count, not the call count. Existing in-car destinations affect route
costs but do not increase this denominator. Signed states (`1` and `-1`) use
the existing route policy. Since 2026-09-30, `state=0` is treated as direction-free
at the objective boundary: each car-subset cost compares both initial service
directions and retains the smaller total passenger wait (UP on an exact tie).
This is not an unrestricted optimization over all stop orders. Boarding/
alighting timing and GA operators are unchanged, and the minimizing direction
is not yet propagated to the simulator (section 9).

Per-car **total** waiting costs reuse the destination objective's route helper.
Each car reads only its own assigned passenger groups and fixed snapshot
parameters, so costs are separable. The inter-floor time remains the shared
`1 / cars[0].velocityFps`. DP enumerates all subsets (including empty ones),
uses strict minimum comparisons, traces back an assignment and checks it with
the direct objective. The local direction minimum for a `state=0` car remains
separable; its route alternatives are evaluated independently for each subset,
without changing the DP recurrence. Its cost table has `C * 2**m` entries;
transition cost is `O(C * 3**m)`. The initial layer and final full-set layer
are simplified exactly.

Default guards are 16 calls and 120 seconds **per candidate**. Both can be
changed in the dialog. Timeout, cancellation, invalid input and call limits
never yield an `optimal` reference or a successful scenario. These are resource
guards, not theoretical limits. No compiled backend or new dependency is used.

HC retains uniform independent initial car labels, random coordinate order,
all car alternatives, first-index tie breaking, strict improvement by `1e-12`,
and at most 100 sweeps per restart. Stops at the sweep budget are recorded separately from
no-improvement stops. Exact success uses `abs(value - optimum) <= 1e-9` seconds,
with relative tolerance zero; zero hits are valid. A result below the optimum
beyond this tolerance is an error. Zero waiting passengers are rejected.

Generation stages:

- Optional legacy `batch_best` screening (default 150 restarts, seed 11);
  set screening restarts to 0 to disable this heuristic filter.
- One bounded exact solve for each screened candidate.
- Exact-reference **selection** (default 1000 restarts, seed 12). This is not
  holdout validation, even though the legacy API argument is `confirm_restarts`.
- Seed 13 is reserved for a later holdout evaluation, not executed or used for
  acceptance. All three seeds are configurable and must differ.

Existing 3–10%, 20–40%, 55–75% target bands have NOT been recalibrated for the exact
reference, the updated HC budget, or the idle-direction objective change.
The measured rate is specific to this objective, HC and budget, not
an algorithm-independent difficulty score. Wilson 95% intervals apply to a
fixed instance/protocol and do not correct scenario-selection bias. Separate
holdout seeds are not a substitute for separate calibration/holdout scenarios.

The workbook's `.meta.json` (schema 2) records objective/model identity, ordered
calls, counts, physics, workbook/content/source hashes, Git revision and dirty
state, exact status/assignment/timings/limits, HC protocol, stage seeds/budgets,
individual outcomes/stopping reasons, hit counts/rate and Wilson interval.
`best_cost` / `best_objective_seconds` continue to mean the best **observed HC**
value; `optimum_cost` / `optimum_objective_seconds` are separate exact values.
Old untagged records are interpreted as `batch_best`, never relabelled exact.
Both new files are staged before publication; ordinary write failures restore
prior outputs. This is not power-failure atomicity across two files.

Solve one existing snapshot without resampling (stdout is a JSON report):

```powershell
.\.venv\Scripts\python.exe analysis\solve_exact_snapshot.py --snapshot initials_files\initials_file.xlsx --seconds 120 --max-calls 16 --stop-over 7 --door-open 2 --velocity-fps 0.5
```

Use `--output path\new_report.json` to save a report without overwriting an
existing file. A non-optimal status exits with code 2 and includes the phase and
timings; no heuristic fallback occurs. This is the objective optimum, not a
measured dynamic-simulation optimum.

For a **newly generated schema-2 workbook**, append a later holdout measurement
without altering the recorded selection or target band:

```python
from scenario_generation import evaluate_saved_scenario
measurement = evaluate_saved_scenario("path/generated.xlsx", restarts=1000)
print(measurement.success_count, measurement.runs, measurement.success_percent,
      measurement.wilson95_percent)
```

This uses the reserved seed. A subsequent call needs another unused seed via
`seed=...`. Changed workbook contents, physics or source semantics invalidate
the saved reference. Legacy batch-best records cannot be used as exact inputs.

The default measurement budget is now 1000 restarts with up to 100 sweeps each
(2026-09-29), shared by the GUI selection control and selection/holdout APIs.
The optional screening count stays at 150; its HC runs also use the 100-sweep
cap. Early stopping on a non-improving full sweep is unchanged. Previous
600-restart/40-sweep measurements describe a different protocol; existing
reports are not rewritten and source-hash checks still reject stale metadata.

Small regression checks (synthetic fixtures, no full-size solves):

```powershell
.\.venv\Scripts\python.exe tests\test_obj_fun_destination.py
.\.venv\Scripts\python.exe tests\test_exact_assignment.py
.\.venv\Scripts\python.exe tests\test_scenario_generation.py
.\.venv\Scripts\python.exe tests\test_scenario_creator_dialog.py
```

## 6. Exact Dispatcher as a simulation control method

In **Control Method**, **Exact Dispatcher (Subset DP)** appears immediately
before **Markov Decision Process**. This is a `Dispatcher` subclass backed by
the same exact solver, not a metaheuristic or an HC difficulty measurement.
The objective is fixed to **Destination Information / WT**, minimizing estimated
mean **passenger** waiting time. The dropdown is locked while Exact is selected;
the previous objective is restored when leaving it. GA settings are hidden and
are not used. Exact-method selection and limits are included in saved UI state;
old settings without these fields load with defaults.

The method has its own maximum-call and time-per-decision controls, defaulting
to 16 calls / 120 seconds. Only a completed optimum is applied. Time/call limits,
invalid input and cancellation never apply partial assignments or silently
switch to another method. The existing background experiment worker keeps the
GUI responsive; the status bar shows cost/DP progress and **Terminate** cancels
an in-progress solve without an error dialog.

Recommended first use: select **Load Custom Initials File**, **No new passenger**
in Traffic Configuration, and **Dispatch when new call registered** in
Simulation Configuration, then start. With no new arrivals and no periodic
dispatch, this gives a one-shot initial decision. Every later decision would solve a fresh
snapshot, so frequent re-dispatch can be costly. Pending-boarding snapshots are
explicitly unsupported: during door opening, passengers can still be waiting
after their hall call has moved to served. The adapter refuses to silently
reinterpret these committed passengers as new assignment decisions.

The solver assumes unlimited capacity, but selecting it does **not** modify the
simulation's capacity or passenger-transfer model. Choose sufficient simulation
capacity for an unconstrained one-shot experiment. The optimum is a model
estimate, not a guarantee about measured dynamic-simulation waiting times.

`decision/exact_dispatcher.py` converts current runtime data to an isolated
`DestinationInstance`, preserving fractional car floors, car-specific stop-over
times, cabin destinations, and the objective's shared first-car inter-floor
time. It maps zero-based solver indices to actual `cars[index].id` values and
assigns whole floor-direction groups. It does not change list order or car
states while solving. Inherited `Dispatcher.run()` performs service-list/state
updates only after successful assignment.

For `state=0`, the shared objective now prices the better of the two initial
service directions, but the solver result still contains only call-to-car
assignments, not chosen directions. Runtime state updates still apply their
existing policy. Consequently the simulated initial direction and service
order need not match the direction used for the reported optimum. Direction
handoff and the runtime `state=0` eligibility invariant remain deferred work.

The most recent solver result and gene order are available as
`dispatcher.last_result` and `dispatcher.last_call_order`; `last_status` is
`no_calls` when there is nothing to assign (not a fabricated zero optimum).
For programmatic use, pass `should_cancel` and/or `progress` callbacks to the
constructor. GUI start/terminate wiring supplies these automatically.

Checks using small synthetic snapshots, including an actual GUI worker run:

```powershell
.\.venv\Scripts\python.exe tests\test_exact_dispatcher.py
.\.venv\Scripts\python.exe tests\test_gui_exact_dispatcher.py
```

## 7. Passenger waiting-time endpoints (2026-09-29)

Primary passenger `WT` and `Pawt` now end when the doors of the car that
**accepts that passenger** start opening at pickup. A full car that refuses
the passenger does not end their wait. A passenger joining that accepting
service while its doors are opening or open has zero primary wait.
This adopts the waiting-time endpoint of ISO 8100-32:2020, 3.40
([definition](https://cdn.standards.iteh.ai/samples/73084/bc9b7ff8d7e7420f95430ea15e57b3c1/ISO-8100-32-2020.pdf#page=13));
it is not a claim that the whole simulator implements that standard.

The engine records an actual `doorOpeningStartTime`, not
`BT - doorOpeningTime`. Capacity-based acceptance reserves the place and
freezes primary WT while the passenger remains in `pendingBoard` and the
waiting list. Existing same-floor counter restarts during opening/open
transfer retain that service's original timestamp; a closing/expired cycle
starts a new event. Thus restarted cycles and fractional times do not require
a nominal-duration subtraction. Physical simulation time remains discretized
by `Ts`, as before.

`WT_board = BT - QJT` retains the previous queue-to-boarding measure as a
secondary metric. `BT`, `DAT`, `TrT`, `TTD`, capacity, movement, door/transfer
timing, and animations are unchanged. Passengers still become `travelling`
at fully-open doors (transfer-animation start), not at opening start or at
transfer end. Consequently `TTD = WT_board + TrT`; it is not generally
`WT + TrT`. Destination-arrival timing has not been redefined.

The GUI reports both waiting measures. Results Excel files keep the original
passenger/HC tables in their original positions and append an
`Average Passenger Wait to Boarding` table, plus a `Metric definitions`
sheet. New simulation records identify `waiting_time_endpoint` as
`pickup_door_opening_start`. Recorded Traffic replay clears prior journey
outcomes on the copied passenger and calculates fresh timestamps; it does
not change the source recording. Existing results are not retrospectively
converted or made directly comparable by subtracting a constant.

Both objectives now estimate travel plus **full earlier stop-overs**, with
no opening/transfer/closing time added at the pickup stop. This supersedes
the earlier full-open objective variant from the same date. A same-floor
pickup costs zero even when `doorOpeningTime = 2`. Conventional remains
call-weighted; Destination remains passenger-weighted. Negative-result checks,
the empty-prefix/shared-reversal-stop fixes, and idle policies were unchanged
by this waiting-time update (see the subsequent objective changes below).
Exact/HC/GA use the same updated objectives; their search algorithms are
unchanged. These remain static estimates, not guarantees about dynamic traffic.

Finite, nonnegative `doorOpeningTime` remains part of car physics validation
and snapshot metadata. `door_opening_time` and CLI `--door-open` remain
supported, but do not add a pickup cost. `stop_over_time` already includes
opening/transfer/closing at earlier stops; do not subtract the opening there.
Scenario, exact-report and GA-sweep metadata identify the new endpoint.
Changed source hashes invalidate previous exact references: reevaluate them
under the new definition before reusing a difficulty or optimum claim.

Focused checks (small fixtures, no calibration or large experiments):

```powershell
.\.venv\Scripts\python.exe tests\test_passenger_waiting_time.py
.\.venv\Scripts\python.exe tests\test_gui_waiting_metrics.py
.\.venv\Scripts\python.exe tests\test_obj_fun_conventional1.py
.\.venv\Scripts\python.exe tests\test_obj_fun_destination.py
```

Verification on 2026-09-29: the 13 new engine waiting tests, 2 new GUI metric
tests, 28 objective tests, smoke/record-replay/Excel checks, and the small
exact, scenario, GA and boarding-renderer integration suites passed.
The separate, unchanged `test_flow_platform.py` fails at its legacy 4-column
expectation (the renderer has two 2-cell hall lanes, giving 6 columns with
2 cars). The same failure was reproduced with both test and renderer loaded
from Git HEAD; it predates this change and was left outside this work's scope.

## 8. Conventional objective: independent chromosome evaluation (2026-09-29)

`objFunConventional1` now starts each chromosome/car pair with a local
`state = car.state`. Idle direction selection and all route branches use this
local value; the supplied fleet is not modified. The existing direction rule,
including the upward tie-break, is unchanged. This removes the MATLAB-style
leak of an idle-direction decision into later chromosome rows.

The regression example now scores candidates A and B as `[2, 2]`, not
`[2, 5]`; B also scores 2 when evaluated alone. Tests cover population
permutation, splitting into batches, duplicate candidates, repeated calls,
unchanged inputs, and the preserved idle-direction policy. Prior stop counts,
pickup waiting-time definition, and the dispatcher's copy wrapper are unchanged.
Destination, Exact/HC algorithms and simulation timing were not modified by
this Conventional-objective fix. The subsequent Destination change is in
section 9.

Historical Conventional GA scores/rankings affected by the leak must be
reevaluated before comparison with the corrected objective. Existing result
files are not rewritten.

## 9. Destination objective: local idle-direction minimization (2026-09-30)

`car_waiting_times()` now treats `state=0` as direction-free at the objective
boundary. It evaluates the existing three-segment route for both initial
directions and returns the **complete route's** waiting arrays with the smaller
total assigned-passenger waiting time. Exact ties prefer UP. A signed input
state (`1` or `-1`) keeps its existing single-direction calculation. The caller
is responsible for supplying a consistent state; load/transfer eligibility is
not checked here.

The single-direction helper `_car_waiting_times_for_direction()` receives an
explicit local `direction` and has fresh working arrays and stop counters on
each call. Neither `car.state` nor passenger inputs are modified. The return
contract remains `(wt_up, wt_down)`: no chosen-direction output is added yet.
Negative waiting checks, shared reversal-stop corrections and the pickup
door-opening-start endpoint are preserved.

Selection uses `wt_up.sum() + wt_down.sum()` over every assigned passenger,
not an unweighted call average or independent minima for individual
passengers. All returned waiting times belong to the same selected route.

DP, Destination/WT GA and HC automatically use this updated shared cost
definition; their search code is unchanged. For a given assignment, the
objective minimizes each direction-free car's cost over its two initial
service directions. A completed DP then finds the exact minimum over call
assignments under this updated static model. GA and HC search the same cost
function but do not thereby acquire an optimality guarantee. Historical
idle-car objective values/exact references need reevaluation under the new
semantics; changed source hashes invalidate saved exact references, and
existing result files are not rewritten.

`Controller.operate`, runtime state updates, and `ExactDispatcher` are NOT
changed. Propagating and enforcing the minimizing direction in the simulator
is deferred: the lower static objective value does not establish that the
simulator executes that route.

### Small regression examples

Both cases use 8 floors, one initially empty car at floor 4 with `state=0`
and `DF=set()`, unlimited capacity, `velocityFps=0.5`, and `stopOverTime=2`.
The UP call is `5 -> 6`; the DOWN call is `2 -> 1`. Values below are static
mean passenger waiting times in seconds, not measured simulation results.

| UP / DOWN passengers | Fixed UP input | Fixed DOWN input | New state=0 result |
| --- | ---: | ---: | ---: |
| 1 / 1 | 9.0 | 11.0 | 9.0 (UP route) |
| 1 / 4 | 13.2 | 6.8 | 6.8 (DOWN route) |

The first case's selected passenger waits are `[2, 16]`, not the incompatible
passenger-wise minima `[2, 4]`. The second case selects `[18, 4, 4, 4, 4]`.
The input car state remains 0 in both cases.

### Verification recorded on 2026-09-30

Seven regression tests were added: six for the objective and one for the
exact solver. They cover both winning directions, passenger weighting,
UP tie-breaking, preservation of signed directions, empty/single-direction
subsets, unchanged inputs, population-order independence, and a tiny exhaustive
comparison of assignments and fixed direction pairs. Existing zero-wait,
negative-wait rejection, and both shared-reversal-stop tests remain intact.

The new UP-choice regression and joint direction-enumeration check failed
against the old idle-as-down implementation, then passed after the change.
The following **78 focused tests passed**; this is not a full-suite claim.

| Test script | Passed |
| --- | ---: |
| `tests/test_obj_fun_destination.py` | 23 |
| `tests/test_exact_assignment.py` | 15 |
| `tests/test_scenario_generation.py` | 14 |
| `tests/test_exact_dispatcher.py` | 10 |
| `tests/test_metaheuristic_dispatcher.py` | 8 |
| `tests/test_ga.py` | 7 |
| `tests/test_ga_custom_initials_e2e.py` | 1 |
| **Total** | **78** |

Reproduce these focused checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -B tests\test_obj_fun_destination.py
.\.venv\Scripts\python.exe -B tests\test_exact_assignment.py
.\.venv\Scripts\python.exe -B tests\test_scenario_generation.py
.\.venv\Scripts\python.exe -B tests\test_exact_dispatcher.py
.\.venv\Scripts\python.exe -B tests\test_metaheuristic_dispatcher.py
.\.venv\Scripts\python.exe -B tests\test_ga.py
.\.venv\Scripts\python.exe -B tests\test_ga_custom_initials_e2e.py
```

These checks use small fixtures and temporary outputs. The default 1000-restart
measurement-loop test mocks the HC run; it does not perform a large calibration.
No large experiment or difficulty-band calibration was run for this change.
The pre-existing renderer-test issue recorded in section 7 was not addressed.
