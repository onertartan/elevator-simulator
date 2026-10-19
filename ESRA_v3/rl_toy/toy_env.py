"""Toy simulator that follows the RULES OF THE DESIGN DOCUMENT (not ESRA's engine).

Purpose: check claims of the design review numerically.
  - 1 tick = 1 s, speed 0.5 floor/s (positions kept in half-floor integers)
  - door counter 7 -> 0 ; transfer (alight + board) when the counter reaches 5 ;
    decision epoch when the counter reaches 2 ; car moves only at counter 0
  - decision epochs: (i) new call, (ii) a counter reached 2          [doc 3.4]
  - a stop starts only if arrival at CH produces a transfer            [doc 3.4]
  - only groups ASSIGNED to the car board; whole group boards          [doc 4.2]
  - waiting ends at counter 5 (boarding instant)                       [doc 4.3]
  - NC-R mask: CH in K_olay(c) = cabin destinations U origins of waiting groups
    assigned to c; any floor if that set is empty                      [doc 5.1]
  - mid-flight reversal allowed, no capacity, no direction rule        [doc 3.3, 4.2]

mask_mode:
  "new"      CH mask computed from the NEW assignment (sequential / consistent)
  "old"      CH mask computed from the assignment BEFORE this action (doc 7.3 option 3)
  "expanded" CH mask = cabin destinations U origins of ALL waiting groups (doc 7.3 option 4)
"""
from __future__ import annotations

import numpy as np


class Pax:
    __slots__ = ("o", "d", "t_arr", "t_board", "t_alight", "car", "n_reassign", "wrong_way")

    def __init__(self, o, d, t):
        self.o, self.d, self.t_arr = o, d, t
        self.t_board = self.t_alight = None
        self.car = None
        self.n_reassign = 0
        self.wrong_way = 0          # seconds spent moving AWAY from destination while on board


class Car:
    __slots__ = ("pos2", "counter", "ch", "onboard", "last_dir")

    def __init__(self, floor):
        self.pos2 = 2 * floor
        self.counter = 0
        self.ch = floor
        self.onboard = []
        self.last_dir = 0


class Toy:
    def __init__(self, F=6, C=4, lam=0.1, t_gen=1800, t_end=3600, seed=0, mask_mode="new",
                 arrivals=None, heartbeat=False):
        self.heartbeat = heartbeat      # stalled system (work pending, no car can produce an event) -> epoch each tick
        self.heartbeats = 0
        self.F, self.C, self.lam, self.t_gen, self.t_end = F, C, lam, t_gen, t_end
        self.rng = np.random.default_rng(seed)
        self.mask_mode = mask_mode
        self.t = 0
        starts = np.round(np.linspace(1, F, C)).astype(int)
        self.cars = [Car(int(f)) for f in starts]
        self.groups = {}            # (o, d) -> list[Pax] waiting
        self.assign = {}            # (o, d) -> car index (physical reservation)
        self.all = []
        self.epochs = 0
        self.wait_ps = 0            # waiting passenger-seconds (reward = -this)
        self.ride_ps = 0            # in-car passenger-seconds
        self.empty_stops = 0        # door cycles that ended with no boarding and no alighting
        self.loaded_reversals = 0   # direction changes with passengers on board
        self.ch_changes = 0
        self.just_finished = set()  # cars whose counter reached 2 since last epoch
        self.new_groups = set()
        if arrivals is None:        # pre-generate: (time, o, d), Poisson, uniform OD
            arrivals = []
            for t in range(t_gen):
                for _ in range(self.rng.poisson(lam)):
                    o = int(self.rng.integers(1, F + 1))
                    d = int(self.rng.integers(1, F))
                    d = d if d < o else d + 1
                    arrivals.append((t, o, d))
        self.arrivals = arrivals
        self._ai = 0

    # ---- helpers -------------------------------------------------------------
    def k_olay(self, c, assign):
        """Event floors of car c under a given assignment (doc 5.1)."""
        s = {p.d for p in self.cars[c].onboard}
        s |= {od[0] for od, lst in self.groups.items() if lst and assign.get(od) == c}
        return s

    def ch_mask(self, c, assign_old, assign_new):
        if self.mask_mode == "new":
            s = self.k_olay(c, assign_new)
        elif self.mask_mode == "old":
            s = self.k_olay(c, assign_old)
        elif self.mask_mode == "expanded":
            s = {p.d for p in self.cars[c].onboard} | {od[0] for od, l in self.groups.items() if l}
        else:                       # none: CH never masked
            return list(range(1, self.F + 1))
        return sorted(s) if s else list(range(1, self.F + 1))

    def active(self):
        return [od for od, lst in self.groups.items() if lst]

    def work_left(self):
        return bool(self.active()) or any(c.onboard for c in self.cars)

    def stalled(self):
        """Work remains but no car can ever produce another event without a new call."""
        if not self.work_left():
            return False
        for i, c in enumerate(self.cars):
            if c.counter != 0 or c.pos2 != 2 * c.ch:
                return False
            floor = c.ch
            if any(p.d == floor for p in c.onboard) or any(
                    lst and od[0] == floor and self.assign.get(od) == i
                    for od, lst in self.groups.items()):
                return False
        return True

    # ---- one decision epoch --------------------------------------------------
    def apply(self, new_assign, new_ch):
        for od in self.active():
            old = self.assign.get(od)
            new = new_assign[od]
            if old is not None and old != new:
                for p in self.groups[od]:
                    p.n_reassign += 1
            self.assign[od] = new
        for i, c in enumerate(self.cars):
            if new_ch[i] != c.ch:
                self.ch_changes += 1
            c.ch = new_ch[i]
        self.epochs += 1
        self.just_finished = set()
        self.new_groups = set()

    # ---- physics: advance until the next decision epoch -----------------------
    def run_until_epoch(self):
        """Returns True if an epoch is pending, False if the horizon ended."""
        while self.t < self.t_end:
            t = self.t
            if self._ai >= len(self.arrivals) and not self.work_left():
                return False                            # drained: every passenger delivered
            epoch = bool(self.just_finished)
            while self._ai < len(self.arrivals) and self.arrivals[self._ai][0] == t:
                _, o, d = self.arrivals[self._ai]
                self._ai += 1
                p = Pax(o, d, t)
                self.all.append(p)
                lst = self.groups.setdefault((o, d), [])
                if not lst:
                    self.assign.pop((o, d), None)       # a fresh group has no reservation yet
                    self.new_groups.add((o, d))
                lst.append(p)
                epoch = True
            if self.heartbeat and not epoch and self.stalled():
                self.heartbeats += 1
                epoch = True
            if epoch:
                return True
            self._tick()
        return False

    def _tick(self):
        t = self.t
        self.wait_ps += sum(len(l) for l in self.groups.values())
        self.ride_ps += sum(len(c.onboard) for c in self.cars)
        for i, c in enumerate(self.cars):
            f2 = 2 * c.ch
            if c.counter == 0:
                if c.pos2 == f2:
                    floor = c.ch
                    transfer = any(p.d == floor for p in c.onboard) or any(
                        lst and od[0] == floor and self.assign.get(od) == i
                        for od, lst in self.groups.items())
                    if transfer:
                        c.counter = 7
                else:
                    step = 1 if f2 > c.pos2 else -1
                    if c.onboard and c.last_dir and step != c.last_dir:
                        self.loaded_reversals += 1
                    for p in c.onboard:
                        if (p.d * 2 - c.pos2) * step < 0:
                            p.wrong_way += 1
                    c.pos2 += step
                    c.last_dir = step
                    continue
            if c.counter > 0:
                c.counter -= 1
                if c.counter == 5:                       # doors open: alight, then board
                    floor = c.pos2 // 2
                    n = 0
                    for p in [p for p in c.onboard if p.d == floor]:
                        p.t_alight = t + 1
                        c.onboard.remove(p)
                        n += 1
                    for od, lst in self.groups.items():
                        if lst and od[0] == floor and self.assign.get(od) == i:
                            for p in lst:
                                p.t_board = t + 1
                                p.car = i
                                c.onboard.append(p)
                                n += 1
                            self.groups[od] = []
                    if n == 0:
                        self.empty_stops += 1
                    c.last_dir = 0
                elif c.counter == 2:
                    self.just_finished.add(i)
        self.t = t + 1

    # ---- summary -------------------------------------------------------------
    def stats(self):
        n = len(self.all)
        boarded = [p for p in self.all if p.t_board is not None]
        done = [p for p in self.all if p.t_alight is not None]
        wt_all = [(p.t_board if p.t_board is not None else self.t_end) - p.t_arr for p in self.all]
        jt_all = [(p.t_alight if p.t_alight is not None else self.t_end) - p.t_arr for p in self.all]
        ride = sum((p.t_alight - p.t_board) for p in done)
        wrong = sum(p.wrong_way for p in self.all)
        return dict(
            n=n, boarded=len(boarded) / max(n, 1), delivered=len(done) / max(n, 1),
            wt_mean=float(np.mean(wt_all)) if n else 0.0,          # censored at horizon
            jt_mean=float(np.mean(jt_all)) if n else 0.0,          # censored at horizon
            wait_ps=self.wait_ps, ride_ps=self.ride_ps, epochs=self.epochs,
            reassign_per_pax=float(np.mean([p.n_reassign for p in self.all])) if n else 0.0,
            ch_changes=self.ch_changes, empty_stops=self.empty_stops,
            loaded_reversals=self.loaded_reversals,
            wrong_way_share=wrong / max(self.ride_ps, 1),
            heartbeats=self.heartbeats,
        )
