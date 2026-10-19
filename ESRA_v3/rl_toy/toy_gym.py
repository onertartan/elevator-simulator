"""Gymnasium wrapper of the toy simulator: the design's observation/action layout with the
assignment -> CH dependency resolved by two zero-duration micro-steps (phase 0: assignment,
phase 1: CH masked by K_olay under the NEW assignment). Stock MaskablePPO, no custom policy."""
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from toy_env import Toy

T_REF = 300.0


class ToyGym(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, F=4, C=2, lam=0.05, t_gen=600, t_cap=2400, w_wait=1.0, w_ride=0.0,
                 scale=0.01, n_max=10, fixed_seed=None, show_prev_assign=True,
                 ch_mask=True, heartbeat=False):
        self.show_prev_assign = show_prev_assign   # phase-0 content: O1 (True) / O0 (False) semantics
        # ch_mask: True/"new" = consistent mask from the new assignment; "expanded" = cabin destinations
        # U origins of ALL waiting groups (assignment-independent); False/"none" = CH never masked
        self.ch_mask = {True: "new", False: "none"}.get(ch_mask, ch_mask)
        self.heartbeat = heartbeat
        self.F, self.C, self.lam, self.t_gen, self.t_cap = F, C, lam, t_gen, t_cap
        self.w_wait, self.w_ride, self.scale, self.n_max = w_wait, w_ride, scale, n_max
        self.fixed_seed = fixed_seed
        self.ods = [(o, d) for o in range(1, F + 1) for d in range(1, F + 1) if o != d]
        self.N = len(self.ods)
        self.nvec = [C + 1] * self.N + [F + 1] * C
        self.action_space = spaces.MultiDiscrete(self.nvec)
        hi_t = math.log1p(t_cap) / math.log1p(T_REF) + 0.01
        self.observation_space = spaces.Dict({
            "calls": spaces.Box(0.0, max(hi_t, 2.0), (self.N, 4 + C), np.float32),
            "cars": spaces.Box(0.0, max(hi_t, 2.0), (C, 5 * F + 2), np.float32),
            "globals": spaces.Box(0.0, 2.0, (4,), np.float32),
        })
        self.env = None
        self.phase = 0
        self.pending = {}

    # -- helpers -------------------------------------------------------------
    def _lt(self, x):
        return math.log1p(max(x, 0.0)) / math.log1p(T_REF)

    def _lc(self, n):
        return min(math.log1p(n) / math.log1p(self.n_max), 2.0)

    def _obs(self):
        e, F, C = self.env, self.F, self.C
        calls = np.zeros((self.N, 4 + C), np.float32)
        shown = self.pending if self.phase == 1 else (e.assign if self.show_prev_assign else {})
        for k, od in enumerate(self.ods):
            lst = e.groups.get(od)
            if lst:
                w = [e.t - p.t_arr for p in lst]
                calls[k, :4] = (self._lc(len(lst)), self._lt(np.mean(w)), self._lt(min(w)), self._lt(max(w)))
                if od in shown:
                    calls[k, 4 + shown[od]] = 1.0
        cars = np.zeros((C, 5 * F + 2), np.float32)
        for i, c in enumerate(e.cars):
            cars[i, c.pos2 - 2] = 1.0
            b = 2 * F - 1
            cars[i, b] = float(c.pos2 == 2 * c.ch)
            cars[i, b + 1] = c.counter / 7.0
            cars[i, b + 2] = self._lc(len(c.onboard))
            for f in range(1, F + 1):
                r = [e.t - p.t_board for p in c.onboard if p.d == f]
                if r:
                    cars[i, b + 3 + 3 * (f - 1): b + 6 + 3 * (f - 1)] = (
                        self._lc(len(r)), self._lt(np.mean(r)), self._lt(max(r)))
        g = np.array([min(e.t / self.t_cap, 1.0), self._lc(sum(len(l) for l in e.groups.values())),
                      self._lc(sum(len(c.onboard) for c in e.cars)), float(self.phase)], np.float32)
        return {"calls": calls, "cars": cars, "globals": g}

    def action_masks(self):
        e, F, C = self.env, self.F, self.C
        m = np.zeros(sum(self.nvec), dtype=bool)
        for k, od in enumerate(self.ods):
            seg = m[k * (C + 1):(k + 1) * (C + 1)]
            if not e.groups.get(od):
                seg[0] = True
            elif self.phase == 0:
                seg[1:] = True
            else:
                seg[1 + self.pending[od]] = True       # phase 1: assignment already fixed
        base = self.N * (C + 1)
        for i in range(C):
            seg = m[base + i * (F + 1): base + (i + 1) * (F + 1)]
            if self.phase == 0:
                seg[0] = True                           # CH not decided in the assignment phase
            else:
                for f in self._legal(i):
                    seg[f] = True
        return m

    def _legal(self, i):
        e, F = self.env, self.F
        if self.ch_mask == "none":
            return list(range(1, F + 1))
        if self.ch_mask == "expanded":
            k = {p.d for p in e.cars[i].onboard} | {od[0] for od, l in e.groups.items() if l}
        else:
            k = e.k_olay(i, self.pending)
        return sorted(k) if k else list(range(1, F + 1))

    # -- gym API -------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        s = self.fixed_seed if self.fixed_seed is not None else int(self.np_random.integers(2**31))
        self.env = Toy(self.F, self.C, self.lam, self.t_gen, self.t_cap, seed=s,
                       mask_mode=self.ch_mask, heartbeat=self.heartbeat)
        self._w = self._r = 0
        alive = self.env.run_until_epoch()
        assert alive
        self._enter_epoch()
        return self._obs(), {}

    def _enter_epoch(self):
        self.pending = {}
        if self.env.active():
            self.phase = 0
        else:
            self.phase = 1

    def step(self, action):
        e, C, F = self.env, self.C, self.F
        action = np.asarray(action)
        if self.phase == 0:
            # max(.., 0) only guards unmasked random actions (env checker); masked policies never hit it
            self.pending = {od: max(int(action[k]) - 1, 0)
                            for k, od in enumerate(self.ods) if e.groups.get(od)}
            self.phase = 1
            return self._obs(), 0.0, False, False, {}
        ch = []
        for i, a in enumerate(action[self.N:]):
            legal = self._legal(i)
            ch.append(int(a) if int(a) in legal else legal[0])   # guard for unmasked actions only
        e.apply(dict(self.pending), ch)
        alive = e.run_until_epoch()
        dw, dr = e.wait_ps - self._w, e.ride_ps - self._r
        self._w, self._r = e.wait_ps, e.ride_ps
        reward = -(self.w_wait * dw + self.w_ride * dr) * self.scale
        info = {}
        if not alive:
            info["stats"] = e.stats()
            self.phase = 1
            self.pending = {}
            return self._obs(), reward, True, False, info
        self._enter_epoch()
        return self._obs(), reward, False, False, info
