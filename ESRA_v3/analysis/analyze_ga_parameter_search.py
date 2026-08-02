"""
analysis/analyze_ga_parameter_search.py
========================================
One-shot analysis of the MATLAB GA parameter-search results for the
paper "Analysis for Optimal Parameters, Selection & Crossover Methods,
Crossover and Mutation Functions for Elevator Dispatching using GA".

Input: matlab_src/results/sonuclarGA.mat holding the 6-D `fitnesses`
tensor written by matlab_src/decision/meta/GA.m's parameterSearch sweep.
Axis order = the nested loop in GA.m (idx1..idx6):

    (Pc, Pm, selection, crossover fn, mutation fn, run)
     6 x 5 x    3      x      3      x      5     x R

Each cell is min(state.Score) at GA completion - the run's best
estimated mean waiting time (seconds, lower = better).

Outputs under analysis/output/ :

  Tables (CSV, and LaTeX when pandas supports it)
    top10_configurations.*   best 10 configs, mean/std/median/min over runs
    marginal_means.*         mean +- std per level of every factor
    factor_effects.*         one-way ANOVA F, p, eta^2 and Kruskal-Wallis
                             per factor (balanced full factorial ->
                             main effects are orthogonal, so eta^2 is
                             each factor's exact share of total SS)
  Figures (PDF + 300 dpi PNG, light mode, validated palette)
    fig_main_effects         5-panel marginal means +- SEM
    fig_pc_pm_heatmap        Pc x Pm mean cost (sequential blue)
    fig_sel_cross_heatmap    selection x crossover mean cost
    fig_mut_pm_interaction   mutation function x Pm interaction lines
    fig_top10_box            run distributions of the top 10 configs
    fig_mutation_box         run distributions per mutation function
  Stats
    stats_summary.txt        headline numbers, Friedman omnibus,
                             winner vs MATLAB-default and winner vs
                             top-10 Mann-Whitney U with Holm correction

Usage (from the ESRA_v3/ root):
    .venv/Scripts/python analysis/analyze_ga_parameter_search.py
        [--mat PATH] [--out DIR]
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
from scipy.io import loadmat

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ---- design (factor levels, GA.m lines 27-31) -------------------------
PC = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
PM = [0.01, 0.02, 0.05, 0.1, 0.2]
SEL = ["stochunif", "roulette", "tournament"]
CROSS = ["scattered", "singlepoint", "twopoint"]
MUT = ["uniform", "block", "scramble", "swap", "frequency"]
FACTORS = [("Pc", PC), ("Pm", PM), ("Selection", SEL),
           ("Crossover fn", CROSS), ("Mutation fn", MUT)]
# MATLAB ga() defaults, as a grid point: Pc=0.8, Pm=0.01,
# stochunif + scattered + uniform
DEFAULT_IDX = (PC.index(0.8), PM.index(0.01), 0, 0, 0)

# ---- palette (dataviz reference instance, light mode) -----------------
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
CAT = ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a"]  # slots 1-5
MARKERS = ["o", "s", "^", "D", "v"]      # secondary encoding for print
SEQ = LinearSegmentedColormap.from_list("seqblue", [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281",
    "#0d366b"])
BOX_FILL = "#9ec5f4"                     # sequential step 200

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8,
    "axes.labelcolor": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "text.color": INK,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def _save(fig, out, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"), dpi=300,
                    bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.pdf/.png")


def _table(df, out, name, float_format="%.3f"):
    df.to_csv(os.path.join(out, f"{name}.csv"))
    try:
        tex = df.to_latex(float_format=float_format)
        with open(os.path.join(out, f"{name}.tex"), "w",
                  encoding="utf-8") as f:
            f.write(tex)
        print(f"  wrote {name}.csv/.tex")
    except Exception as exc:                     # LaTeX export is optional
        print(f"  wrote {name}.csv  (LaTeX skipped: {exc})")


def load_fitnesses(path):
    """Return the 6-D fitnesses tensor from the .mat file."""
    m = loadmat(path)
    if "fitnesses" in m:
        F = np.asarray(m["fitnesses"], dtype=float)
    else:                       # fall back to any 6-D double array
        cands = [v for k, v in m.items() if not k.startswith("__")
                 and isinstance(v, np.ndarray) and v.ndim == 6]
        if not cands:
            raise SystemExit(
                f"No 6-D array found in {path}; variables: "
                f"{[k for k in m if not k.startswith('__')]}")
        F = np.asarray(cands[0], dtype=float)
    expected = (len(PC), len(PM), len(SEL), len(CROSS), len(MUT))
    if F.shape[:5] != expected:
        raise SystemExit(f"fitnesses shape {F.shape} does not match the "
                         f"GA.m design {expected} x runs")
    return F


def tidy(F):
    """One row per GA run: factors + run + cost."""
    runs = F.shape[5]
    recs = []
    for (i1, pc), (i2, pm), (i3, se), (i4, cr), (i5, mu) in \
            itertools.product(enumerate(PC), enumerate(PM),
                              enumerate(SEL), enumerate(CROSS),
                              enumerate(MUT)):
        for r in range(runs):
            recs.append((pc, pm, se, cr, mu, r + 1, F[i1, i2, i3, i4, i5, r]))
    df = pd.DataFrame(recs, columns=["Pc", "Pm", "Selection",
                                     "Crossover fn", "Mutation fn",
                                     "run", "cost"])
    for name, levels in FACTORS[2:]:
        df[name] = pd.Categorical(df[name], categories=levels, ordered=True)
    return df


def config_label(row):
    return (f"Pc {row['Pc']:g} Pm {row['Pm']:g} "
            f"{row['Selection'][:5]}+{row['Crossover fn'][:7]}"
            f"+{row['Mutation fn']}")


# ----------------------------------------------------------------------
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--mat", default=os.path.join(
        root, "matlab_src", "results", "sonuclarGA.mat"))
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    F = load_fitnesses(args.mat)
    runs = F.shape[5]
    df = tidy(F)
    mean6 = F.mean(axis=5)                     # (6,5,3,3,5)
    print(f"Loaded {args.mat}\n  shape {F.shape}: "
          f"{mean6.size} configurations x {runs} runs "
          f"= {F.size} GA executions\n")
    lines = [f"GA parameter search: {mean6.size} configurations x "
             f"{runs} runs = {F.size} executions",
             f"cost = best estimated mean waiting time (s); lower is better",
             ""]

    # ---- per-configuration stats + top 10 -----------------------------
    g = df.groupby(["Pc", "Pm", "Selection", "Crossover fn",
                    "Mutation fn"], observed=True)["cost"]
    cfg = g.agg(mean="mean", std="std", median="median",
                min="min", max="max").reset_index()
    cfg["mean+std"] = cfg["mean"] + cfg["std"]
    cfg = cfg.sort_values("mean").reset_index(drop=True)
    top10 = cfg.head(10).copy()
    top10.index = np.arange(1, 11)
    top10.index.name = "rank"
    _table(top10, args.out, "top10_configurations")

    best = cfg.iloc[0]
    lines += ["WINNER (lowest mean over runs):",
              f"  Pc={best['Pc']:g}  Pm={best['Pm']:g}  "
              f"{best['Selection']} + {best['Crossover fn']} + "
              f"{best['Mutation fn']}",
              f"  mean {best['mean']:.3f} s  std {best['std']:.3f}  "
              f"median {best['median']:.3f}  "
              f"range [{best['min']:.3f}, {best['max']:.3f}]", ""]

    # ---- MATLAB-default comparison ------------------------------------
    d = DEFAULT_IDX
    def_runs = F[d[0], d[1], d[2], d[3], d[4], :]
    win_runs = df[(df["Pc"] == best["Pc"]) & (df["Pm"] == best["Pm"])
                  & (df["Selection"] == best["Selection"])
                  & (df["Crossover fn"] == best["Crossover fn"])
                  & (df["Mutation fn"] == best["Mutation fn"])
                  ]["cost"].to_numpy()
    u, p = stats.mannwhitneyu(win_runs, def_runs, alternative="less")
    impr = 100 * (def_runs.mean() - win_runs.mean()) / def_runs.mean()
    lines += ["MATLAB-DEFAULT configuration "
              "(Pc=0.8, Pm=0.01, stochunif+scattered+uniform):",
              f"  mean {def_runs.mean():.3f} s  std {def_runs.std(ddof=1):.3f}",
              f"  winner improves on it by {impr:.1f} %  "
              f"(one-sided Mann-Whitney U={u:.0f}, p={p:.4g})", ""]

    # ---- marginal means (main effects) --------------------------------
    blocks = []
    for name, levels in FACTORS:
        mm = (df.groupby(name, observed=True)["cost"]
              .agg(mean="mean", std="std", sem="sem"))
        mm = mm.reindex(levels)
        mm.insert(0, "factor", name)
        mm.index.name = "level"
        blocks.append(mm.reset_index())
    marginal = pd.concat(blocks, ignore_index=True)[
        ["factor", "level", "mean", "std", "sem"]]
    _table(marginal.set_index(["factor", "level"]), args.out,
           "marginal_means")

    # ---- factor effects: ANOVA + eta^2 + Kruskal-Wallis ---------------
    y = df["cost"].to_numpy()
    ss_total = ((y - y.mean()) ** 2).sum()
    rows = []
    for name, levels in FACTORS:
        groups = [df.loc[df[name] == lv, "cost"].to_numpy()
                  for lv in levels]
        f_stat, p_f = stats.f_oneway(*groups)
        ss_b = sum(len(gr) * (gr.mean() - y.mean()) ** 2 for gr in groups)
        h, p_kw = stats.kruskal(*groups)
        rows.append((name, f_stat, p_f, ss_b / ss_total, h, p_kw))
    eff = pd.DataFrame(rows, columns=["factor", "F", "p (ANOVA)",
                                      "eta^2", "H", "p (Kruskal-Wallis)"]
                       ).set_index("factor").sort_values("eta^2",
                                                         ascending=False)
    _table(eff, args.out, "factor_effects", float_format="%.4g")
    lines += ["FACTOR EFFECTS (balanced design -> eta^2 = exact share "
              "of total variance):"]
    for name, r in eff.iterrows():
        lines.append(f"  {name:<12} eta^2={r['eta^2']:.4f}  "
                     f"F={r['F']:.1f} p={r['p (ANOVA)']:.3g}  "
                     f"KW H={r['H']:.1f} p={r['p (Kruskal-Wallis)']:.3g}")
    lines.append("")

    # ---- Friedman omnibus over configurations (runs as blocks) --------
    flat = F.reshape(-1, runs)
    chi2, p_fr = stats.friedmanchisquare(*flat)
    lines += [f"Friedman omnibus across {flat.shape[0]} configurations "
              f"(runs as blocks): chi2={chi2:.1f}, p={p_fr:.3g}",
              "  (blocks are matched only if runs shared seeds across "
              "configurations; otherwise read as approximate and rely "
              "on Kruskal-Wallis above)", ""]

    # ---- winner vs the rest of the top 10, Holm-corrected -------------
    ps, labels = [], []
    for _, row in top10.iloc[1:].iterrows():
        rr = df[(df["Pc"] == row["Pc"]) & (df["Pm"] == row["Pm"])
                & (df["Selection"] == row["Selection"])
                & (df["Crossover fn"] == row["Crossover fn"])
                & (df["Mutation fn"] == row["Mutation fn"])
                ]["cost"].to_numpy()
        _, p_i = stats.mannwhitneyu(win_runs, rr, alternative="less")
        ps.append(p_i)
        labels.append(config_label(row))
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(ps) - rank) * ps[i])
        adj[i] = min(1.0, running)
    lines.append("WINNER vs ranks 2-10 (one-sided Mann-Whitney, "
                 "Holm-adjusted):")
    for lab, p_i, a_i in zip(labels, ps, adj):
        verdict = "significant" if a_i < 0.05 else "not significant"
        lines.append(f"  vs {lab:<38} p={p_i:.4f}  "
                     f"p_holm={a_i:.4f}  {verdict}")
    lines += ["", "NOTE: all runs optimize the same dispatch snapshot; "
              "consider replicating the top configs on 2-3 further "
              "traffic snapshots for external validity."]

    with open(os.path.join(args.out, "stats_summary.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("  wrote stats_summary.txt\n")

    # =================== figures ======================================
    # ---- 1) main effects ---------------------------------------------
    fig, axes = plt.subplots(1, 5, figsize=(12, 2.7), sharey=True)
    for ax, (name, levels) in zip(axes, FACTORS):
        mm = marginal[marginal["factor"] == name]
        x = np.arange(len(levels))
        ax.errorbar(x, mm["mean"], yerr=mm["sem"], color=CAT[0],
                    marker="o", markersize=5, linewidth=2, capsize=3)
        ax.set_xticks(x)
        labels_ = [f"{lv:g}" if isinstance(lv, float) else str(lv)
                   for lv in levels]
        rot = 0 if isinstance(levels[0], float) else 30
        ax.set_xticklabels(labels_, rotation=rot,
                           ha="right" if rot else "center")
        ax.set_title(name, color=INK)
        ax.grid(axis="y")
    axes[0].set_ylabel("mean best cost (s)")
    fig.suptitle("Main effects (marginal mean ± SEM over all other "
                 "factors and runs)", color=INK, y=1.04)
    _save(fig, args.out, "fig_main_effects")

    # ---- 2) Pc x Pm heatmap ------------------------------------------
    for name, mat, xl, yl, xt, yt in (
            ("fig_pc_pm_heatmap", mean6.mean(axis=(2, 3, 4)),
             "Pm (mutation rate)", "Pc (crossover fraction)", PM, PC),
            ("fig_sel_cross_heatmap",
             mean6.mean(axis=(0, 1, 4)), "crossover function",
             "selection function", CROSS, SEL)):
        fig, ax = plt.subplots(
            figsize=(4.4, 3.2) if name.startswith("fig_pc") else (3.8, 3.0))
        im = ax.imshow(mat, cmap=SEQ, aspect="auto")
        ax.set_xticks(np.arange(len(xt)))
        ax.set_xticklabels([f"{v:g}" if isinstance(v, float) else v
                            for v in xt],
                           rotation=0 if isinstance(xt[0], float) else 20,
                           ha="center" if isinstance(xt[0], float)
                           else "right")
        ax.set_yticks(np.arange(len(yt)))
        ax.set_yticklabels([f"{v:g}" if isinstance(v, float) else v
                            for v in yt])
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        lo, hi = mat.min(), mat.max()
        bi, bj = np.unravel_index(np.argmin(mat), mat.shape)
        for (i, j), v in np.ndenumerate(mat):
            frac = (v - lo) / (hi - lo) if hi > lo else 0.0
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=7.5,
                    color="white" if frac > 0.55 else INK,
                    fontweight="bold" if (i, j) == (bi, bj) else "normal")
        ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False,
                                   edgecolor=INK, linewidth=1.6))
        cb = fig.colorbar(im, ax=ax, shrink=0.9)
        cb.set_label("mean best cost (s)", color=INK2)
        cb.outline.set_edgecolor(AXIS)
        ax.set_title("lower is better; box = best cell", color=INK2,
                     fontsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        _save(fig, args.out, name)

    # ---- 3) mutation fn x Pm interaction -----------------------------
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for k, mu in enumerate(MUT):
        yv = mean6[:, :, :, :, k].mean(axis=(0, 2, 3))   # over Pc,sel,cross
        ax.plot(PM, yv, color=CAT[k], marker=MARKERS[k], markersize=6,
                linewidth=2, label=mu)
    ax.set_xscale("log")
    ax.set_xticks(PM)
    ax.set_xticklabels([f"{v:g}" for v in PM])
    ax.minorticks_off()
    ax.set_xlabel("Pm (mutation rate, log scale)")
    ax.set_ylabel("mean best cost (s)")
    ax.grid(axis="y")
    ax.legend(title="mutation fn", frameon=False, fontsize=8,
              title_fontsize=8)
    _save(fig, args.out, "fig_mut_pm_interaction")

    # ---- 4) top-10 box plots -----------------------------------------
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    data, ylabels = [], []
    for _, row in top10.iloc[::-1].iterrows():        # best at the top
        rr = df[(df["Pc"] == row["Pc"]) & (df["Pm"] == row["Pm"])
                & (df["Selection"] == row["Selection"])
                & (df["Crossover fn"] == row["Crossover fn"])
                & (df["Mutation fn"] == row["Mutation fn"])
                ]["cost"].to_numpy()
        data.append(rr)
        ylabels.append(config_label(row))
    bp = ax.boxplot(data, orientation="horizontal", patch_artist=True,
                    widths=0.6,
                    medianprops=dict(color=INK, linewidth=1.6),
                    boxprops=dict(facecolor=BOX_FILL, edgecolor=AXIS),
                    whiskerprops=dict(color=MUTED),
                    capprops=dict(color=MUTED),
                    flierprops=dict(marker="o", markersize=3,
                                    markerfacecolor=MUTED,
                                    markeredgecolor=MUTED))
    ax.set_yticklabels(ylabels, fontsize=7.5)
    ax.set_xlabel(f"best cost over {runs} runs (s)")
    ax.set_title("Top-10 configurations (rank 1 at top)", color=INK2,
                 fontsize=8.5)
    ax.grid(axis="x")
    _save(fig, args.out, "fig_top10_box")

    # ---- 5) per-mutation-function box plots --------------------------
    fig, ax = plt.subplots(figsize=(5.0, 3.2))
    data = [df.loc[df["Mutation fn"] == mu, "cost"].to_numpy()
            for mu in MUT]
    bp = ax.boxplot(data, patch_artist=True, widths=0.55,
                    medianprops=dict(color=INK, linewidth=1.6),
                    whiskerprops=dict(color=MUTED),
                    capprops=dict(color=MUTED),
                    flierprops=dict(marker="o", markersize=2.5,
                                    markerfacecolor=MUTED,
                                    markeredgecolor=MUTED))
    for patch, c in zip(bp["boxes"], CAT):
        patch.set_facecolor(c)
        patch.set_alpha(0.75)
        patch.set_edgecolor(AXIS)
    ax.set_xticklabels(MUT, rotation=20, ha="right")
    ax.set_ylabel("best cost (s)")
    ax.set_title("All runs pooled per mutation function "
                 f"(n={len(df) // len(MUT)} each)", color=INK2,
                 fontsize=8.5)
    ax.grid(axis="y")
    _save(fig, args.out, "fig_mutation_box")

    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
