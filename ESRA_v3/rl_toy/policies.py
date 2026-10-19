"""Policies for the toy simulator (all respect the env's CH mask)."""
import numpy as np


def random_full(env, rng):
    """Design as written: every active group and every car re-decided at every epoch."""
    old = dict(env.assign)
    new = {od: int(rng.integers(env.C)) for od in env.active()}
    ch = []
    for c in range(env.C):
        m = env.ch_mask(c, old, new)
        ch.append(int(m[rng.integers(len(m))]))
    return new, ch


def random_commit(env, rng):
    """Same randomness, but commitments persist: only NEW groups are assigned, and a car
    re-chooses its target only when it just finished a stop or its target became invalid."""
    old = dict(env.assign)
    new = {od: (old[od] if od in old else int(rng.integers(env.C))) for od in env.active()}
    ch = []
    for c, car in enumerate(env.cars):
        k = sorted(env.k_olay(c, new))
        if not k:
            ch.append(car.ch)
        elif c in env.just_finished or car.ch not in k:
            ch.append(int(k[rng.integers(len(k))]))
        else:
            ch.append(car.ch)
    return new, ch


def _nearest_car_assign(env):
    old = dict(env.assign)
    new = {}
    for od in env.active():
        if od in old:
            new[od] = old[od]
        else:
            new[od] = int(np.argmin([abs(c.pos2 - 2 * od[0]) for c in env.cars]))
    return new


def make_heuristic(kind):
    """kind: 'scan' (collective sweep), 'nearest' (nearest event floor),
    'pickup_first' (nearest assigned pickup while any exists, deliveries only afterwards)."""
    sweep = {}

    def policy(env, rng=None):
        new = _nearest_car_assign(env)
        ch = []
        for c, car in enumerate(env.cars):
            drops = {p.d for p in car.onboard}
            picks = {od[0] for od, lst in env.groups.items() if lst and new.get(od) == c}
            k = drops | picks
            if not k:
                ch.append(car.ch if car.pos2 != 2 * car.ch else car.pos2 // 2)
                continue
            pos = car.pos2 / 2
            if kind == "nearest":
                ch.append(min(k, key=lambda f: (abs(f - pos), f)))
            elif kind == "pickup_first":
                src = picks if picks else drops
                ch.append(min(src, key=lambda f: (abs(f - pos), f)))
            else:  # scan
                d = sweep.get(c, 1)
                here = [f for f in k if f == pos and car.counter == 0]
                ahead = [f for f in k if (f - pos) * d > 0]
                if here:
                    ch.append(here[0])
                elif ahead:
                    ch.append(min(ahead, key=lambda f: abs(f - pos)))
                else:
                    d = -d
                    sweep[c] = d
                    back = [f for f in k if (f - pos) * d > 0] or list(k)
                    ch.append(min(back, key=lambda f: abs(f - pos)))
        return new, ch
    return policy


def run(env, policy, rng=None):
    while env.run_until_epoch():
        new, ch = policy(env, rng)
        env.apply(new, ch)
    return env.stats()
