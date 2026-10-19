import sys, json, time
sys.path.insert(0, '.')
import numpy as np
import torch
torch.set_num_threads(1)
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv
from toy_gym import ToyGym
from toy_env import Toy
from policies import run, random_full, make_heuristic

tag, w_ride, total = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
F, C, LAM, TG, TC = int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), 600, 2400
EVAL_SEEDS = list(range(1000, 1040))
flags = sys.argv[7].lower().split(",") if len(sys.argv) > 7 else []
kw = dict(F=F, C=C, lam=LAM, t_gen=TG, t_cap=TC, w_ride=w_ride,
          show_prev_assign="o0" not in flags,
          ch_mask="none" if "nomask" in flags else ("expanded" if "expanded" in flags else "new"),
          heartbeat="hb" in flags)

def evaluate(model):
    rows = []
    for s in EVAL_SEEDS:
        env = ToyGym(fixed_seed=s, **kw)
        obs, _ = env.reset()
        done = False
        while not done:
            a, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
            obs, r, done, _, info = env.step(a)
        rows.append(info["stats"])
    return rows

def summ(rows):
    f = lambda k: float(np.mean([r[k] for r in rows]))
    return dict(WT=round(f("wt_mean"), 2), JT=round(f("jt_mean"), 2), delivered=round(f("delivered"), 3),
                wrong_way=round(f("wrong_way_share"), 3), reassign=round(f("reassign_per_pax"), 2),
                empty_stops=round(f("empty_stops"), 2))

out = {"config": dict(kw, total=total), "baselines": {}, "curve": []}
for name, pol in (("random_full", random_full), ("scan", make_heuristic("scan")),
                  ("nearest", make_heuristic("nearest")), ("pickup_first", make_heuristic("pickup_first"))):
    rows = []
    for s in EVAL_SEEDS:
        e = Toy(F, C, LAM, TG, TC, seed=s, mask_mode="new")
        p = make_heuristic(name) if name != "random_full" else pol
        rows.append(run(e, p, np.random.default_rng(s)))
    out["baselines"][name] = summ(rows)
print(tag, "baselines", json.dumps(out["baselines"]), flush=True)

venv = DummyVecEnv([lambda i=i: ToyGym(**kw) for i in range(4)])
model = MaskablePPO("MultiInputPolicy", venv, gamma=1.0, gae_lambda=0.95, n_steps=512, batch_size=256,
                    n_epochs=10, learning_rate=3e-4, ent_coef=0.01, seed=0, device="cpu", verbose=0)
t0 = time.time(); done_steps = 0; chunk = 50_000
while done_steps < total:
    model.learn(total_timesteps=chunk, reset_num_timesteps=False)
    done_steps += chunk
    s = summ(evaluate(model)); s["steps"] = done_steps; s["minutes"] = round((time.time() - t0) / 60, 1)
    out["curve"].append(s)
    print(tag, json.dumps(s), flush=True)
    json.dump(out, open(f"ppo_{tag}.json", "w"), indent=1)
