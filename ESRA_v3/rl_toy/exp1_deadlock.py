import sys; sys.path.insert(0, '.')
import numpy as np
from toy_env import Toy
from policies import run, random_full

def lazy(env, rng=None):
    """Mask-legal but unhelpful: assign every group to car 0, each car keeps its current
    target whenever the mask allows it, otherwise takes the first allowed floor."""
    old = dict(env.assign); new = {od: 0 for od in env.active()}
    ch = []
    for c, car in enumerate(env.cars):
        m = env.ch_mask(c, old, new)
        ch.append(car.ch if car.ch in m else m[0])
    return new, ch

def swap(env, rng=None):
    """Two groups, each assigned to the car that is NOT sent to it (legal under 'expanded')."""
    old = dict(env.assign); new = {(2, 3): 0, (3, 2): 1}
    new = {od: new[od] for od in env.active()}
    want = [3, 2]
    ch = []
    for c, car in enumerate(env.cars):
        m = env.ch_mask(c, old, new)
        ch.append(want[c] if want[c] in m else m[0])
    return new, ch

print("A) one passenger 2->3 at t=0, cars at floors 1 and 4, horizon 600 s, policy 'lazy'")
for mode in ("new", "old", "expanded"):
    e = Toy(F=4, C=2, t_gen=1, t_end=600, mask_mode=mode, arrivals=[(0, 2, 3)])
    s = run(e, lazy)
    print(f"   mask={mode:9s} boarded={s['boarded']:.0%} delivered={s['delivered']:.0%} "
          f"waiting pax-seconds={s['wait_ps']:4d} epochs={s['epochs']} stalled_at_end={e.stalled()}")
print("B) two passengers (2->3 -> car0, 3->2 -> car1), policy sends each car to the OTHER group's floor")
for mode in ("new", "old", "expanded"):
    e = Toy(F=4, C=2, t_gen=1, t_end=600, mask_mode=mode, arrivals=[(0, 2, 3), (0, 3, 2)])
    s = run(e, swap)
    print(f"   mask={mode:9s} boarded={s['boarded']:.0%} delivered={s['delivered']:.0%} "
          f"waiting pax-seconds={s['wait_ps']:4d} epochs={s['epochs']} stalled_at_end={e.stalled()}")
print("C) uniformly random masked policy, F=6 C=4, Poisson 1 pax / 20 s for 600 s, horizon 3600 s, 200 seeds")
for mode in ("new", "old", "expanded"):
    stalled = unserved = total = 0
    for seed in range(200):
        e = Toy(F=6, C=4, lam=0.05, t_gen=600, t_end=3600, seed=seed, mask_mode=mode)
        s = run(e, random_full, np.random.default_rng(10_000 + seed))
        stalled += e.stalled(); total += s['n']; unserved += round(s['n'] * (1 - s['delivered']))
    print(f"   mask={mode:9s} episodes ending in a permanent stall: {stalled}/200 ; "
          f"passengers never delivered: {unserved}/{total} ({unserved/total:.1%})")
