"""
tests/test_cc_rule_vs_engine.py
===============================
Run from the ESRA_v3/ root:  python tests/test_cc_rule_vs_engine.py

The collective-control (CC) stop and boarding rule of the exact-solution
reference code (analysis/esra_dp_ref.py, mode 'CC') against the real engine.

Setting: one car, empty, standing at an integer floor; every passenger is
assigned to it at t=0 and the assignment never changes. Doors 2+3+2, Ts=1,
0.5 floor/s. The engine is driven with the fixture of
test_pending_board_direction.py (real Car / Controller, experiment.py tick
order).

Claim checked: the (WT, TTD) the engine measures for every passenger equals
the (boarding time, alighting time) of ONE of the stop plans the CC rule
allows. The rule allows more than one plan only where an empty car has
assigned work on both sides: the direction is then a decision of the RL
policy (design decision K20), and the engine's own choice (nearest call,
ties upwards; keep the direction while work remains ahead) must be one of
the allowed plans.

The rule for a stop at which the cabin becomes empty:
  - assigned work remains ahead in the travel direction (a same-direction
    call at this floor, or any call further on): the car keeps its
    direction; an opposite-direction call at this floor is not taken in
    this stop;
  - nothing remains ahead: the car reverses in this stop and the
    opposite-direction call at this floor is accepted in the same door
    cycle (no extra time).

Not covered here: cars that start loaded, moving or inside a door cycle;
the capacity limit; several cars. PR and PRR are not engine modes.
"""
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from analysis import esra_dp_ref as ref                  # reference code, not engine code
from test_pending_board_direction import _World          # one car, real Car / Controller

N_SCENARIOS = 1000
SEED = 20261118


def engine_times(start_floor, passengers, t_max=600):
    """Per passenger (WT, TTD) as measured by the engine; None if it does not finish."""
    w = _World(start_floor=float(start_floor))
    ps = [w.assign(origin, destination) for origin, destination in passengers]
    while w.t < t_max and any(p.DAT is None for p in ps):
        w.tick()
    if any(p.DAT is None for p in ps):
        return None
    return [(p.WT, p.TTD) for p in ps]


def rule_times(start_floor, passengers):
    """For every stop plan the CC rule allows: per passenger (boarding time, alighting time)."""
    car = (start_floor, ())
    groups = tuple((origin, destination, 1) for origin, destination in passengers)
    for plan in ref.all_plans(car, groups, set(range(len(groups))), 'CC'):
        t, floor, board, alight = 0, start_floor, {}, {}
        for stop_floor, boarders in plan:
            t += ref.T_FLOOR * abs(stop_floor - floor)
            floor = stop_floor
            for i in board:
                if i not in alight and groups[i][1] == stop_floor:
                    alight[i] = t
            for i in boarders:
                board[i] = t
            t += ref.T_STOP
        yield [stop_floor for stop_floor, _ in plan], [(board[i], alight[i]) for i in range(len(groups))]


def same_times(rule, engine):
    return all(float(b) == wt and float(a) == ttd for (b, a), (wt, ttd) in zip(rule, engine))


class CcRuleVsEngineTests(unittest.TestCase):

    def test_fixture_and_reference_use_the_same_timing(self):
        car = _World().car
        self.assertEqual(car.stopOverTime, ref.T_STOP)
        self.assertEqual(1 / car.velocityFps, ref.T_FLOOR)

    def test_reversal_in_the_same_stop_when_nothing_is_left_ahead(self):
        """Empty car at 2; p: 3 -> 5, g: 5 -> 3. The cabin empties at 5 with no
        work above: the car turns in that stop, g is accepted in the same door
        cycle (t=13) and the stop takes the normal 7 s."""
        passengers = [(3, 5), (5, 3)]
        self.assertEqual(engine_times(2, passengers), [(2.0, 13.0), (13.0, 24.0)])
        self.assertEqual(list(rule_times(2, passengers)), [([3, 5, 3], [(2, 13), (13, 24)])])

    def test_no_reversal_while_work_remains_ahead(self):
        """Same, plus q: 6 -> 7. Work remains above when the cabin empties at
        5: the engine goes on to 6 and 7, g waits for the car's return (t=42)."""
        passengers = [(3, 5), (5, 3), (6, 7)]
        engine = engine_times(2, passengers)
        self.assertEqual(engine, [(2.0, 13.0), (42.0, 53.0), (22.0, 31.0)])
        plans = dict((tuple(stops), times) for stops, times in rule_times(2, passengers))
        self.assertTrue(same_times(plans[(3, 5, 6, 7, 5, 3)], engine))
        # the rule also allows the policy's other choice at 5 (turn for g in a second stop)
        self.assertEqual(set(plans), {(3, 5, 6, 7, 5, 3), (3, 5, 5, 3, 6, 7)})

    def test_random_scenarios_match_a_permitted_plan(self):
        rnd = random.Random(SEED)
        with_choice = 0
        for k in range(N_SCENARIOS):
            floors = rnd.choice((6, 8, 10))
            start = rnd.randint(1, floors)
            passengers = []
            for _ in range(rnd.randint(1, 5)):
                origin = rnd.randint(1, floors)
                passengers.append((origin, rnd.choice([f for f in range(1, floors + 1) if f != origin])))
            engine = engine_times(start, passengers)
            self.assertIsNotNone(engine, f"scenario {k}: engine did not finish; start {start}, {passengers}")
            plans = list(rule_times(start, passengers))
            with_choice += len({tuple(times) for _, times in plans}) > 1
            self.assertTrue(
                any(same_times(times, engine) for _, times in plans),
                f"scenario {k}: start {start}, passengers {passengers}\n"
                f"  engine (WT, TTD): {engine}\n"
                + "\n".join(f"  rule {stops}: {times}" for stops, times in plans))
        # the direction choice of an empty car was exercised, not only forced routes
        self.assertGreater(with_choice, N_SCENARIOS // 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
