# ESRA — MATLAB → Python Elevator Simulator Port: PROJECT STATUS

Historical port notes: the sections below describe the July 2026 baseline,
not current feature coverage. See RUNNING.md for current usage and semantics.

Waiting-time update (2026-09-29): RUNNING.md section 7 supersedes the WT
definitions, reference WT values and smoke-test advice below. Primary WT now
ends at the accepting car's pickup opening START; WT_board retains the former
queue-to-boarding measure. For the reference trip: WT/Pawt=2, WT_board=4,
BT=4, DAT=15, TrT=11. The updated smoke suite passes. Animation and physical
timing have not changed; do not restore the historical WT=4 assertions.

Last updated: 2026-07-18 — after phased boarding [A4]/[S10]/[N4].

---

## 1. Current state

Runnable end-to-end with the **Nearest Car Method**: GUI → Start →
pyqtgraph animation → Excel results. Record (dataType 1) and replay
(dataType 2) work. Stack: PySide6 / pyqtgraph / NumPy / pandas+openpyxl.

Recent behavior changes (both intentional, fully tested):

* **Phased alighting** ([A1]-[A3], [S8]/[S9], [N3], [D10]): passengers
  alight when the doors finish opening, walk to the right-most
  "landing platform" column during passengerTransferTime, and vanish
  at transfer end.
* **Phased boarding** ([A4], [S10], [N4]): the mirror. Hall calls are
  answered (served) at arrival; the selected boarders stand at their
  hall lane while the doors open (WT still counting), board at the
  door-open moment, and walk lane → cabin during the transfer phase.
  Alighting frees capacity before boarding takes it, so load never
  exceeds capacity on combined stops (retires the [A2] transient-
  overload caveat).

### Door-cycle timeline (doors open/transfer/close = 2+3+2, Ts=1)

```
arrival T      : beginDropoff/beginPickup — DF discarded, HC served,
                 pendingAlight/pendingBoard selected, counter = 7
T .. T+2       : doors opening; boarders stand at hall lane (WT counts)
T+2 (counter 5): DOOR-OPEN — alight() then board() recorded; walkers
                 start (cabin→platform and lane→cabin)
T+2 .. T+5     : transfer phase; walk fraction ramps 0.33/0.67/1.0
T+5 (counter 2): transfer done — all walkers vanish
T+5 .. T+7     : doors closing; car resumes when counter reaches 0
```

updateDoorCycle runs at the end of checkStopOver, before the counter
decrement in Controller.operate, so door-open lands exactly at
arrival + doorOpeningTime (including doorOpeningTime = 0 → arrival tick).

---

## 2. Reference physics (regression anchors)

Smoke scenario: nf=5, 1 passenger floor 2 → 4, deterministic TestTraffic,
doors 2+3+2, user Dispatcher.run moves the car the same tick it is
assigned (see decision/dispatcher.py note — certified against Dispatcher.m).

| Quantity                | Pre-phased | Alighting only | **Current (both)** |
|-------------------------|-----------|----------------|--------------------|
| HC answered / HC.WT     | t=2 / 2.0 | t=2 / 2.0      | **t=2 / 2.0**      |
| Passenger BT            | 2         | 2              | **4**              |
| Pawt (avg passenger WT) | 2.0       | 2.0            | **4.0**            |
| Passenger DAT           | 13        | 15             | **15**             |
| Passenger TrT           | 11        | 13             | **11**             |
| car tripTime            | 6.0       | 6.0            | **6.0**            |
| numOfStops              | 2         | 2              | **2**              |

Rule of thumb: board() and alight() are each recorded at
arrival + doorOpeningTime, so Pawt grows by doorOpeningTime, HCawt is
unchanged (calls answered at arrival), and TrT equals its pre-phased
value (both endpoints shift equally).

### ⚠ KNOWN RED: tests/test_experiment_smoke.py predates phased boarding

Update these assertions to the **Current** column:
1. `exp.Pawt[0, 0, 0, 0] == 2.0`                    → `4.0`
2. `(p.BT, p.DAT, p.TrT) == (2, 13, 11)`            → `(4, 15, 11)`
3. Excel check `ws["B2"].value == 2.0`              → `4.0`  (B5 stays 2.0)
4. Frames check `results[6] == "2.00"` (avg P WT)   → `"4.00"`

---

## 3. Module inventory & ownership

USER-owned conversions (preserve MATLAB quirks, flagged `!!!`, rather
than fixing them): `car.py` (now with Claude's [A1]-[A4] door-cycle
additions; **CRLF line endings — do not normalize**), `building.py`,
`traffic.py`, `data_structures/` (passenger, hall_call, *_lists,
record), `decision/` base classes (decision_maker, dispatcher —
[P3]/[P4]/[P11] fixes noted in-file).

CLAUDE-ported: `experiment.py` [D1]-[D10], `simulator.py` [S1]-[S10],
`controller.py`, `configuration.py`, `data_conf.py`, `main.py`,
`decision/nearest_car_dispatcher.py`, `gui/` (main_window, worker,
flow_view [N1]-[N4]/[V1]-[V7], sprites, tabs/ [L1]-[L3]).

MATLAB references: under `matlab_src/`
for the GA/ACO/PSO/DE ports.

## 4. Deviation-note index

Every intentional divergence from MATLAB is tagged inline; continue the
numbering per family: [A#] car.py door cycle · [D#] experiment.py ·
[S#] simulator.py · [P#] decision/ · [N#]/[V#] gui/flow_view.py ·
[L#] gui/tabs · [T#] traffic tests. Reserved for dispatcher ports:
[G#] GA, [O#] ACO, [W#] PSO, [E#] DE.

Frame contract additions (consumed by flow_view, all optional — frames
without them render as before): `landingPlatform`, per-car `alight`
{DF: count}, `alighting` [ids] + `alightProgress`, `pendingBoard` /
`boarding` [{id, dir}] + `boardProgress`.

## 5. Tests

```
python tests/test_experiment_smoke.py            # engine e2e (see ⚠ above)
python tests/check_real_data_structures.py       # data_structures compat
QT_QPA_PLATFORM=offscreen python tests/test_flow_sprites.py
QT_QPA_PLATFORM=offscreen python tests/test_flow_platform.py   # [N3]
QT_QPA_PLATFORM=offscreen python tests/test_flow_boarding.py   # [N4]
```

## 6. Pending work

1. Update test_experiment_smoke.py anchors (section 2) — first task.
2. Dispatcher ports, one per session: MetaheuristicDispatcher  →GA  → PSO → DE (sources to
   matlab_src/; GUI Control Method tab already collects all parameters;
   main_window raises "Not ported yet" for them). RNG policy: seeded
   numpy Generator parameter, no global state, no bit-identical MATLAB
   randomness — verify operators with fixed-seed unit tests and compare
   dispatchers on identical replayed traffic (dataType 2).
3. MDP control method (GUI present, engine absent). Ignore MDP.
4. dataType 3 (custom initials .xlsx) — raises NotImplemented.
5. Certify same-tick dispatch ordering against original Dispatcher.m.
