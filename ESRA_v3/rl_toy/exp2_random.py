import sys; sys.path.insert(0, '.')
import numpy as np
from toy_env import Toy
from policies import run, random_full, random_commit, make_heuristic

def avg(rows, k): return float(np.mean([r[k] for r in rows]))

def block(F, C, lam, t_gen=1800, t_end=3600, seeds=30):
    print(f"\nF={F} C={C}  Poisson {lam:.3f} pax/s (1 per {1/lam:.0f} s) for {t_gen} s, horizon {t_end} s, {seeds} seeds")
    print(f"  {'policy':22s} {'deliv%':>7s} {'WT':>7s} {'JT':>7s} {'epochs':>7s} {'s/epoch':>8s} {'reassign/pax':>12s} {'CHchg':>6s} {'emptyStop':>9s} {'wrongWay%':>9s}")
    pols = [("random, re-decide all", random_full), ("random, commitments", random_commit),
            ("heur. scan", None), ("heur. nearest", None), ("heur. pickup_first", None)]
    out = {}
    for name, pol in pols:
        rows = []
        for seed in range(seeds):
            e = Toy(F=F, C=C, lam=lam, t_gen=t_gen, t_end=t_end, seed=seed, mask_mode="new")
            p = pol if pol else make_heuristic(name.split()[-1])
            rows.append(run(e, p, np.random.default_rng(777 + seed)))
        out[name] = rows
        print(f"  {name:22s} {100*avg(rows,'delivered'):7.1f} {avg(rows,'wt_mean'):7.1f} {avg(rows,'jt_mean'):7.1f} "
              f"{avg(rows,'epochs'):7.0f} {t_end/avg(rows,'epochs'):8.1f} {avg(rows,'reassign_per_pax'):12.2f} "
              f"{avg(rows,'ch_changes'):6.0f} {avg(rows,'empty_stops'):9.1f} {100*avg(rows,'wrong_way_share'):9.1f}")
    return out

block(4, 2, 1/20)
block(6, 4, 1/20)
block(6, 4, 1/10)
block(6, 8, 1/6)
