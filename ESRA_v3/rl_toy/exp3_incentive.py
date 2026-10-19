import sys; sys.path.insert(0, '.')
import numpy as np
from toy_env import Toy
from policies import run, make_heuristic

def avg(rows, k): return float(np.mean([r[k] for r in rows]))
print("Heuristics under the design's rules (consistent mask). WT/JT in s, censored at horizon; 20 seeds.")
for F, C in ((6, 4), (12, 4), (12, 8)):
    for lam in (0.10, 0.15, 0.20, 0.25, 0.30):
        line = f"F={F:2d} C={C} 1 pax/{1/lam:4.1f}s |"
        for kind in ("scan", "nearest", "pickup_first"):
            rows = []
            for seed in range(20):
                e = Toy(F=F, C=C, lam=lam, t_gen=1800, t_end=5400, seed=seed, mask_mode="new")
                rows.append(run(e, make_heuristic(kind)))
            mx = float(np.mean([r['ride_ps'] / max(r['n'], 1) for r in rows]))
            line += (f" {kind}: WT {avg(rows,'wt_mean'):6.1f} JT {avg(rows,'jt_mean'):7.1f} "
                     f"deliv {100*avg(rows,'delivered'):5.1f}% wrong {100*avg(rows,'wrong_way_share'):4.1f}% |")
        print(line)
