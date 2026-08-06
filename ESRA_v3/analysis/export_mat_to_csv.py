"""
analysis/export_mat_to_csv.py
==============================
Export the GA parameter-search results in matlab_src/results/
sonuclarGA.mat to AI-assistant-friendly formats (CSV / XLSX / TXT),
excluding `Pawt` (per request) and `dataConf` (an opaque MATLAB MCOS
class object that only MATLAB can decode).

Axis order of `fitnesses` = the nested loop in
matlab_src/decision/meta/GA.m: (Pc, Pm, selection, crossover fn,
mutation fn, run).

Outputs under matlab_src/results/export/ :
    fitnesses_long.csv        13,500 rows - one per GA run
    mean_fitnesses_long.csv    1,350 rows - one per configuration
    README.txt                 column/definition sheet
    sonuclarGA_export.xlsx     all three of the above as sheets

Usage (from the ESRA_v3/ root):
    .venv/Scripts/python analysis/export_mat_to_csv.py
"""
from __future__ import annotations

import itertools
import os

import numpy as np
import pandas as pd
from scipy.io import loadmat

PC = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
PM = [0.01, 0.02, 0.05, 0.1, 0.2]
SEL = ["stochunif", "roulette", "tournament"]
CROSS = ["scattered", "singlepoint", "twopoint"]
MUT = ["uniform", "block", "scramble", "swap", "frequency"]

README = """GA parameter-search results - ESRA elevator simulator
=======================================================
Source: sonuclarGA.mat (MATLAB), variable `fitnesses`
(6 x 5 x 3 x 3 x 5 x 10 double). Exported without `Pawt` (excluded on
purpose) and `dataConf` (opaque MATLAB class object).

Experiment: full-factorial sweep of GA operator/parameter settings for
elevator group dispatching (one car label per waiting hall call,
integer encoding). Every configuration was run 10 times; each value is
that run's best objective = estimated mean passenger waiting time in
seconds. LOWER IS BETTER.

fitnesses_long.csv - one row per GA run (13,500 rows):
    Pc            crossover fraction        {0.3, 0.4, 0.5, 0.6, 0.7, 0.8}
    Pm            mutation rate             {0.01, 0.02, 0.05, 0.1, 0.2}
    selection     selection function        {stochunif, roulette, tournament}
    crossover_fn  crossover function        {scattered, singlepoint, twopoint}
    mutation_fn   mutation operator         {uniform, block, scramble, swap,
                                             frequency}
    run           run index                 1..10 (independent RNG streams)
    best_cost_s   best cost of the run      seconds, lower is better

mean_fitnesses_long.csv - one row per configuration (1,350 rows):
    same factor columns, plus
    mean_cost_s   mean of best_cost_s over the 10 runs
    (matches the MATLAB variable `mean_fitnesses`)
"""


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mat = os.path.join(root, "matlab_src", "results", "sonuclarGA.mat")
    out = os.path.join(root, "matlab_src", "results", "export")
    os.makedirs(out, exist_ok=True)

    F = np.asarray(loadmat(mat)["fitnesses"], dtype=float)
    assert F.shape == (6, 5, 3, 3, 5, 10), F.shape

    rows = []
    for (i1, pc), (i2, pm), (i3, se), (i4, cr), (i5, mu) in \
            itertools.product(enumerate(PC), enumerate(PM),
                              enumerate(SEL), enumerate(CROSS),
                              enumerate(MUT)):
        for r in range(F.shape[5]):
            rows.append((pc, pm, se, cr, mu, r + 1,
                         F[i1, i2, i3, i4, i5, r]))
    long = pd.DataFrame(rows, columns=["Pc", "Pm", "selection",
                                       "crossover_fn", "mutation_fn",
                                       "run", "best_cost_s"])
    mean = (long.drop(columns="run")
            .groupby(["Pc", "Pm", "selection", "crossover_fn",
                      "mutation_fn"], sort=False)["best_cost_s"]
            .mean().reset_index()
            .rename(columns={"best_cost_s": "mean_cost_s"}))

    long.to_csv(os.path.join(out, "fitnesses_long.csv"), index=False)
    mean.to_csv(os.path.join(out, "mean_fitnesses_long.csv"), index=False)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README)

    xlsx = os.path.join(out, "sonuclarGA_export.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        pd.DataFrame({"README": README.splitlines()}).to_excel(
            xw, sheet_name="README", index=False)
        long.to_excel(xw, sheet_name="fitnesses_long", index=False)
        mean.to_excel(xw, sheet_name="mean_fitnesses_long", index=False)

    print(f"exported {len(long)} run rows and {len(mean)} config rows to")
    print(f"  {out}")
    for name in ("fitnesses_long.csv", "mean_fitnesses_long.csv",
                 "README.txt", "sonuclarGA_export.xlsx"):
        size = os.path.getsize(os.path.join(out, name))
        print(f"  {name:<28} {size / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
