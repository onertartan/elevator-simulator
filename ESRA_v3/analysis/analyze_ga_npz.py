"""
analyze_ga_npz.py
=================
Analysis of the *Python* GA parameter-search results (dataset B) for the
CIIS 2026 paper "Analysis for Optimal Parameters, Selection & Crossover
Methods, Crossover and Mutation Functions for Elevator Dispatching using
GA".

This replaces the earlier MATLAB-oriented analyze_ga_parameter_search.py.
Differences that matter:

  * input is a .npz written by the parallel Python sweep, not a .mat;
  * the factor levels are read from the sweep's own *_meta.json sidecar
    instead of being hard-coded, so the 7th crossover-rate level (0.9)
    comes in automatically -> 7 x 5 x 3 x 3 x 5 = 1575 configurations,
    100 runs each, 157,500 GA executions;
  * the sweep used common random numbers (seedMode "crn", baseSeed 0), so
    run index r is the SAME scenario seed for every configuration. Paired
    tests are therefore valid here (they were not in the MATLAB sweep,
    which never called rng). The CRN check below quantifies this;
  * every axis limit is derived from the data. The MATLAB script had the
    old AWT range baked in and would silently clip this dataset;
  * the ANOVA table reports rho = sqrt(SS/N), expressed as a percentage of
    the grand mean, next to %SS. %SS is a *share*: when one term grows,
    every other term's share falls even if nothing about it changed. rho
    is an absolute RMS effect in seconds and does not have that problem.
    Reporting only %SS invites exactly the misreading this study has to
    avoid.

Sums of squares are computed directly from the tensor. For a balanced
full factorial that is exact and Type I = Type II = Type III, so there is
nothing to choose. --statsmodels-check refits the same model with
statsmodels and asserts agreement.

Usage:
    python analyze_ga_npz.py --npz PATH [--meta PATH] [--out DIR]
                             [--statsmodels-check]
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from statsmodels.stats.multicomp import pairwise_tukeyhsd

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------
#  design: the recommendation this analysis defends
# ---------------------------------------------------------------------
# The study defines NO baseline dispatcher and NO default GA setting.
# Every comparison below is internal to the grid.
#
# Three independent MATLAB sweeps agreed on 41/41 pairwise factor
# comparisons by direction but their top-10 configuration lists had an
# EMPTY three-way intersection. Picking "the best observed row" is picking
# noise. The recommendation is therefore a BLOCK of the design, with one
# interior point named only for readers who need a single setting to copy.
BLOCK = {
    "Selection": "tournament",
    "Crossover fn": "scattered",
    "Mutation fn": "frequency",
    "Pc": [0.3, 0.4, 0.5],
    "Pm": [0.1, 0.2],
}
POINT = (0.4, 0.2, "tournament", "scattered", "frequency")

# the "label-generating" mutation operators: these can introduce a car
# label absent from the parent chromosome. The other three can only
# rearrange labels already present.
GOOD_MUT = ["frequency", "uniform"]

PRETTY = {"stochunif": "Stochastic uniform", "roulette": "Roulette wheel",
          "tournament": "Tournament", "scattered": "Scattered",
          "singlepoint": "Single point", "twopoint": "Two point",
          "uniform": "Uniform", "block": "Block", "scramble": "Scramble",
          "swap": "Swap", "frequency": "Frequency"}
SHORT = {k: v.replace("Stochastic ", "Stoch. ") for k, v in PRETTY.items()}
AXIS_TITLE = {"Pc": r"Crossover rate $P_c$", "Pm": r"Mutation rate $P_m$",
              "Selection": "Selection method",
              "Crossover fn": "Crossover method",
              "Mutation fn": "Mutation method"}

# ---- palette (CVD-validated, light mode) -----------------------------
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e8e7e3", "#8a8a85"
ORANGE = "#eb6834"
CAT5 = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"]
MARKERS = ["o", "s", "^", "D", "v"]
LINESTYLES = ["-", "--", "-.", (0, (3, 1, 1, 1)), (0, (1, 1))]
SEQ_STEPS = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
             "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
             "#184f95", "#104281", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("seqblue", SEQ_STEPS)
BOX_FILL = "#cde2fb"

plt.rcParams.update({
    "font.family": ["DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8.5,
    "xtick.labelsize": 7.2, "ytick.labelsize": 7.5, "legend.fontsize": 7.2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.7, "axes.labelcolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "grid.color": GRID, "grid.linewidth": 0.6,
    "text.color": INK, "legend.frameon": False, "lines.linewidth": 1.6,
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

# acmart[sigconf]: \textwidth 506.30 pt = 7.03 in, \columnwidth 241.15 pt
# = 3.35 in. Figures are authored at exactly these widths so
# \includegraphics never rescales them.
FULL_W, COL_W = 7.03, 3.35


# =====================================================================
#  io helpers
# =====================================================================
def _save(fig, out, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"), dpi=300,
                    bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.pdf/.png")


def _csv(df, out, name, index=True):
    df.to_csv(os.path.join(out, f"{name}.csv"), index=index)
    print(f"  wrote {name}.csv")


def _tex(text, out, name):
    with open(os.path.join(out, f"{name}.tex"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  wrote {name}.tex")


def _num(x):
    """Thousands separator that LaTeX is happy with."""
    return f"{x:,}".replace(",", "\\,")


def strip_prefix(names, prefixes=("selection", "crossover")):
    """meta.json stores 'selectiontournament' / 'crossoverscattered'."""
    out = []
    for n in names:
        s = str(n)
        for p in prefixes:
            if s.startswith(p) and len(s) > len(p):
                s = s[len(p):]
                break
        out.append(s)
    return out


def load_meta(meta_path, npz_path):
    if meta_path is None:
        cands = sorted(glob.glob(os.path.splitext(npz_path)[0] + "*meta*.json"))
        if not cands:
            d = os.path.dirname(os.path.abspath(npz_path))
            cands = sorted(glob.glob(os.path.join(d, "*meta*.json")))
        if not cands:
            raise SystemExit("No *_meta.json found next to the .npz; pass --meta")
        meta_path = cands[0]
    with open(meta_path, "r", encoding="utf-8-sig") as f:
        meta = json.load(f)
    print(f"meta: {meta_path}")
    return meta, meta_path


def levels_from_meta(meta):
    g = meta["grid"]
    PC = [float(v) for v in g["crossoverValues"]]
    PM = [float(v) for v in g["mutationValues"]]
    SEL = strip_prefix(g["selectionFunctions"])
    CROSS = strip_prefix(g["crossoverFunctions"])
    MUT = [str(v) for v in g["mutationFunctions"]]
    return PC, PM, SEL, CROSS, MUT


def load_fitnesses(path, shape5):
    """Return the 6-D tensor (Pc, Pm, sel, cross, mut, run)."""
    z = np.load(path, allow_pickle=False)
    keys = list(z.files)
    print(f"npz: {path}\n  arrays: {[(k, z[k].shape) for k in keys]}")
    named = [k for k in keys if k.lower() in
             ("fitnesses", "fitness", "results", "costs", "awt", "f")]
    cands = [k for k in (named + keys) if z[k].ndim == 6]
    if not cands:
        raise SystemExit(f"No 6-D array in {path}; arrays: "
                         f"{[(k, z[k].shape) for k in keys]}")
    F = np.asarray(z[cands[0]], dtype=float)
    if F.shape[:5] != tuple(shape5):
        raise SystemExit(f"tensor shape {F.shape} does not match the meta "
                         f"grid {tuple(shape5)} x runs")
    if not np.isfinite(F).all():
        n_bad = int((~np.isfinite(F)).sum())
        raise SystemExit(f"{n_bad} non-finite entries: the sweep did not "
                         f"complete for every configuration")
    return F


# =====================================================================
#  stats helpers
# =====================================================================
def tidy(F, PC, PM, SEL, CROSS, MUT):
    """One row per GA run. Vectorised: 157,500 rows is too many to append."""
    idx = np.indices(F.shape).reshape(6, -1)
    df = pd.DataFrame({
        "Pc": np.asarray(PC, dtype=float)[idx[0]],
        "Pm": np.asarray(PM, dtype=float)[idx[1]],
        "Selection": pd.Categorical(np.asarray(SEL)[idx[2]],
                                    categories=SEL, ordered=True),
        "Crossover fn": pd.Categorical(np.asarray(CROSS)[idx[3]],
                                       categories=CROSS, ordered=True),
        "Mutation fn": pd.Categorical(np.asarray(MUT)[idx[4]],
                                      categories=MUT, ordered=True),
        "run": idx[5].astype(np.int32) + 1,
        "cost": F.reshape(-1),
    })
    return df


def tensor_anova(F):
    """Exact SS decomposition for a balanced full factorial.

    Model: 5 main effects + all 10 two-way interactions. Everything above
    two-way, plus pure run-to-run error, lands in the residual - which is
    what statsmodels' anova_lm reports as Residual for the same formula.

    Balanced design => Type I = Type II = Type III, so there is no
    sequential-vs-marginal choice to make.
    """
    N = F.size
    mu = F.mean()
    ss_total = ((F - mu) ** 2).sum()
    dims = F.shape[:5]
    R = F.shape[5]
    rows = {}

    def collapse(axes_keep):
        """Cell means over the kept factor axes, averaged over the rest."""
        drop = tuple(a for a in range(6) if a not in axes_keep)
        return F.mean(axis=drop)

    # main effects
    main = {}
    for a in range(5):
        m = collapse((a,))                       # (n_a,)
        reps = N // dims[a]
        ss = reps * ((m - mu) ** 2).sum()
        main[a] = m
        rows[(a,)] = (dims[a] - 1, ss)

    # two-way interactions
    for a, b in itertools.combinations(range(5), 2):
        m = collapse((a, b))                     # (n_a, n_b)
        eff = m - main[a][:, None] - main[b][None, :] + mu
        reps = N // (dims[a] * dims[b])
        ss = reps * (eff ** 2).sum()
        rows[(a, b)] = ((dims[a] - 1) * (dims[b] - 1), ss)

    ss_model = sum(v[1] for v in rows.values())
    df_model = sum(v[0] for v in rows.values())
    ss_res = ss_total - ss_model
    df_res = N - 1 - df_model
    return rows, ss_total, ss_res, df_res, mu, N, R


def crn_block_ss(F):
    """SS explained by the run index as a blocking factor.

    Under common random numbers, run r means the same seed for every
    configuration, so a systematic run effect is expected and is EVIDENCE
    that CRN is in force. Without seeding this term is pure noise and
    tests near zero - which is exactly what the MATLAB sweep showed, and
    why paired tests were invalid there.
    """
    N = F.size
    mu = F.mean()
    ss_total = ((F - mu) ** 2).sum()
    R = F.shape[5]
    rm = F.mean(axis=(0, 1, 2, 3, 4))            # (R,)
    ss_run = (N // R) * ((rm - mu) ** 2).sum()
    df_run = R - 1
    # F test against the residual of a main-effects-only-plus-block model:
    # use the full-cell within variation as the error term
    cell_mean = F.mean(axis=5, keepdims=True)
    ss_within = ((F - cell_mean) ** 2).sum()
    df_within = N - F[..., 0].size
    ms_run = ss_run / df_run
    ms_err = (ss_within - ss_run) / (df_within - df_run)
    f_stat = ms_run / ms_err
    p = stats.f.sf(f_stat, df_run, df_within - df_run)
    return dict(ss=ss_run, df=df_run, pct=100 * ss_run / ss_total,
                F=f_stat, p=p, pct_of_within=100 * ss_run / ss_within)


def compact_letters(df, factor, levels, alpha=0.05):
    """Compact letter display from Tukey HSD.

    Built from the MAXIMAL CLIQUES of the 'not significantly different'
    graph (Bron-Kerbosch). A greedy sweep gets this wrong whenever a
    middle level is tied with two levels that differ from each other -
    it produced a demonstrably wrong grouping for the mutation operators
    in an earlier version of this analysis.
    """
    t = pairwise_tukeyhsd(df["cost"].to_numpy(),
                          df[factor].astype(str).to_numpy(), alpha=alpha)
    res = pd.DataFrame(t.summary().data[1:], columns=t.summary().data[0])
    sv = [str(v) for v in levels]
    means = {v: df.loc[df[factor].astype(str) == v, "cost"].mean() for v in sv}
    order = sorted(sv, key=lambda v: means[v])
    nd = {v: {v} for v in sv}
    for _, r in res.iterrows():
        if not r["reject"]:
            a, b = str(r["group1"]), str(r["group2"])
            nd[a].add(b)
            nd[b].add(a)
    cliques = []

    def bron_kerbosch(R, P, X):
        if not P and not X:
            cliques.append(set(R))
            return
        for v in list(P):
            nv = nd[v] - {v}                     # WITHOUT this, infinite recursion
            bron_kerbosch(R | {v}, P & nv, X & nv)
            P = P - {v}
            X = X | {v}

    bron_kerbosch(set(), set(sv), set())
    cliques.sort(key=lambda c: min(order.index(v) for v in c))
    letters = {v: "" for v in sv}
    for i, c in enumerate(cliques):
        for v in c:
            letters[v] += "abcdefghijklmnop"[i]
    return {v: "".join(sorted(letters[v])) for v in sv}, res


def holm(pvals):
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    adj = np.empty(n)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (n - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def benjamini_hochberg(pvals):
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)[::-1]
    adj = np.empty(n)
    running = 1.0
    for rank, i in enumerate(order):
        running = min(running, p[i] * n / (n - rank))
        adj[i] = min(1.0, running)
    return adj


def cell_runs(F, PC, PM, SEL, CROSS, MUT, spec):
    """The R run costs of one configuration, in run order (CRN-aligned)."""
    pc, pm, se, cr, mu_ = spec
    return F[PC.index(pc), PM.index(pm), SEL.index(se),
             CROSS.index(cr), MUT.index(mu_), :]


def tick_labels(name, levels):
    if name in ("Pc", "Pm"):
        return [f"{v:g}" for v in levels], 0, "center"
    return [SHORT[v] for v in levels], 20, "right"


def two_row_axes(figsize, n_pc, n_pm):
    """Row 1: the two numeric settings. Row 2: the three method settings.

    Long operator names do not fit five equal panels across a page width.
    Width ratios track the level counts so the boxes stay the same width
    in every panel (7 Pc levels here, not 6).
    """
    fig = plt.figure(figsize=figsize)
    gs0 = fig.add_gridspec(2, 1, hspace=0.62)
    g1 = gs0[0].subgridspec(1, 2, width_ratios=[n_pc, n_pm], wspace=0.10)
    g2 = gs0[1].subgridspec(1, 3, width_ratios=[3, 3, 5], wspace=0.10)
    a = [fig.add_subplot(g1[0])]
    a.append(fig.add_subplot(g1[1], sharey=a[0]))
    a.append(fig.add_subplot(g2[0], sharey=a[0]))
    a.append(fig.add_subplot(g2[1], sharey=a[0]))
    a.append(fig.add_subplot(g2[2], sharey=a[0]))
    for ax in (a[1], a[3], a[4]):
        plt.setp(ax.get_yticklabels(), visible=False)
    return fig, a


def nice_limits(vals, pad=0.06):
    lo, hi = float(np.min(vals)), float(np.max(vals))
    span = hi - lo
    return lo - pad * span, hi + pad * span


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cikti"))
    ap.add_argument("--statsmodels-check", action="store_true",
                    help="refit the ANOVA with statsmodels and assert "
                         "agreement with the tensor decomposition")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    meta, meta_path = load_meta(args.meta, args.npz)
    PC, PM, SEL, CROSS, MUT = levels_from_meta(meta)
    FACTORS = [("Pc", PC), ("Pm", PM), ("Selection", SEL),
               ("Crossover fn", CROSS), ("Mutation fn", MUT)]
    AX_OF = {name: i for i, (name, _) in enumerate(FACTORS)}

    F = load_fitnesses(args.npz, [len(v) for _, v in FACTORS])
    runs = F.shape[5]
    n_cfg = int(np.prod(F.shape[:5]))
    df = tidy(F, PC, PM, SEL, CROSS, MUT)
    y = df["cost"].to_numpy()
    BKS = float(y.min())

    if int(meta.get("tasksCompleted", F.size)) != F.size:
        print(f"  WARNING: meta tasksCompleted={meta.get('tasksCompleted')} "
              f"but tensor holds {F.size} values")

    # AWT is a mean over the passengers in the snapshot, so every value is
    # an integer number of seconds divided by the passenger count. Recover
    # that count: it is a model constant the paper has to state, and a
    # mismatch means the wrong snapshot was analysed.
    n_pax = None
    for k in range(2, 400):
        if np.allclose(y * k, np.round(y * k), atol=1e-6):
            n_pax = k
            break
    cp = meta.get("carParams", {})
    TF = (cp.get("floorHeight", np.nan) / cp.get("carVelocity", np.nan)
          if cp.get("carVelocity") else float("nan"))
    PT = (cp.get("doorOpeningTime", 0) + cp.get("passengerTransferTime", 0)
          + cp.get("doorClosingTime", 0))

    print(f"\n  {n_cfg} configurations x {runs} runs = {F.size} GA runs")
    print(f"  AWT quantum 1/{n_pax}  ->  {n_pax} passengers in the snapshot")
    print(f"  TF = {TF:g} s, PT = {PT:g} s, population "
          f"{meta.get('populationSize')}, generations {meta.get('generations')}")
    print(f"  seedMode {meta.get('seedMode')} baseSeed {meta.get('baseSeed')}\n")

    _csv(df, args.out, "runs_long", index=False)

    lines = [
        "GA parameter search (dataset B, Python sweep)",
        f"  {n_cfg} configurations x {runs} runs = {F.size} GA executions",
        f"  grid: Pc {PC}, Pm {PM}",
        f"        selection {SEL}, crossover {CROSS}, mutation {MUT}",
        f"  snapshot {meta.get('snapshot')}, {n_pax} passengers "
        f"(AWT is quantised to 1/{n_pax} s)",
        f"  model constants: TF = {TF:g} s, PT = {PT:g} s, "
        f"carCapacity {cp.get('carCapacity')}, "
        f"carCapacityFactor {cp.get('carCapacityFactor')}, "
        f"carVelocity {cp.get('carVelocity')}, "
        f"floorHeight {cp.get('floorHeight')}",
        f"  GA: population {meta.get('populationSize')}, "
        f"generations {meta.get('generations')}, "
        f"seedMode {meta.get('seedMode')}, baseSeed {meta.get('baseSeed')}",
        f"  sweep wall clock {meta.get('elapsedSeconds')} s on "
        f"{meta.get('workers')} workers",
        "",
        "cost = actual average passenger waiting time (s) of the best "
        "solution a run produced; lower is better. Destination control "
        "means arrival floors are known, so this is the realised waiting "
        "time, not an estimate.",
        "",
        f"All runs: mean {y.mean():.4f}  sd {y.std(ddof=1):.4f}  "
        f"min {y.min():.4f}  max {y.max():.4f}",
        f"Distinct AWT values observed: {len(np.unique(y))}",
        f"Best known AWT (BKS) = {BKS:.4f} s = {round(BKS * n_pax)}/{n_pax}, "
        f"reached by {(y <= BKS + 1e-9).mean() * 100:.2f} % of all runs",
        "",
    ]

    # =================================================================
    #  per-configuration statistics
    # =================================================================
    keys = ["Pc", "Pm", "Selection", "Crossover fn", "Mutation fn"]
    g = df.groupby(keys, observed=True)["cost"]
    cfg = g.agg(mean="mean", std="std", median="median",
                min="min", max="max").reset_index()
    cfg["sem"] = cfg["std"] / np.sqrt(runs)
    cfg["hits"] = g.apply(lambda s: int((s <= BKS + 1e-9).sum())).to_numpy()
    cfg["success %"] = cfg["hits"] / runs * 100
    # AWT is quantised, so exact ties on the mean happen. Without a
    # deterministic tie-break the printed ranking contradicts itself
    # between runs of this script.
    cfg = cfg.sort_values(["mean", "hits", "std", "Pc", "Pm"],
                          ascending=[True, False, True, True, True],
                          kind="mergesort").reset_index(drop=True)
    cfg.index = np.arange(1, len(cfg) + 1)
    cfg.index.name = "rank"
    _csv(cfg, args.out, "configurations_all")

    best = cfg.iloc[0]
    worst = cfg.iloc[-1]
    best_spec = tuple(best[k] for k in keys)
    win_runs = cell_runs(F, PC, PM, SEL, CROSS, MUT, best_spec)

    lines += [
        f"{int((cfg['hits'] > 0).sum())} of {n_cfg} configurations reached "
        f"the BKS at least once; best hit count {int(cfg['hits'].max())}/{runs}",
        f"Configuration means span {cfg['mean'].min():.4f} - "
        f"{cfg['mean'].max():.4f} s "
        f"(worst is +{(cfg['mean'].max() / cfg['mean'].min() - 1) * 100:.1f} % "
        f"over best; equivalently {(1 - cfg['mean'].min() / cfg['mean'].max()) * 100:.1f} % "
        f"lower AWT from configuring the same algorithm well)",
        "",
        "RANK 1 (lowest mean) -- reported as ONE MEMBER of the top region, "
        "never as 'the' configuration:",
        f"  Pc={best['Pc']:g} Pm={best['Pm']:g} {best['Selection']} + "
        f"{best['Crossover fn']} + {best['Mutation fn']}",
        f"  mean {best['mean']:.4f}  sd {best['std']:.4f}  "
        f"hits {int(best['hits'])}/{runs}",
        f"RANK {n_cfg} (worst): Pc={worst['Pc']:g} Pm={worst['Pm']:g} "
        f"{worst['Selection']} + {worst['Crossover fn']} + "
        f"{worst['Mutation fn']}, mean {worst['mean']:.4f}",
        "",
    ]

    # =================================================================
    #  marginal means + Tukey compact letter display
    # =================================================================
    blocks, tukey_tables = [], {}
    for name, levels in FACTORS:
        sub = df.groupby(name, observed=True)["cost"]
        mm = sub.agg(mean="mean", std="std", sem="sem", min="min")
        mm["success %"] = sub.apply(lambda s: (s <= BKS + 1e-9).mean() * 100)
        mm = mm.reindex(levels)
        letters, tuk = compact_letters(df, name, levels)
        tukey_tables[name] = tuk
        mm["group"] = [letters[str(lv)] for lv in levels]
        mm.insert(0, "factor", name)
        mm.index.name = "level"
        blocks.append(mm.reset_index())
    marginal = pd.concat(blocks, ignore_index=True)[
        ["factor", "level", "mean", "std", "sem", "min", "success %", "group"]]
    _csv(marginal.set_index(["factor", "level"]), args.out, "marginal_means")

    n_pairs = sum(len(l) * (len(l) - 1) // 2 for _, l in FACTORS)
    lines += [f"PAIRWISE LEVEL COMPARISONS: {n_pairs} "
              f"(= sum of C(levels,2) = "
              f"{'+'.join(str(len(l) * (len(l) - 1) // 2) for _, l in FACTORS)})",
              ""]

    # =================================================================
    #  variance decomposition
    # =================================================================
    ss_rows, ss_total, ss_res, df_res, mu, N, R = tensor_anova(F)
    names5 = [n for n, _ in FACTORS]

    def term_label(key):
        return " x ".join(names5[i] for i in key)

    rec = []
    for key, (dfree, ss) in ss_rows.items():
        ms = ss / dfree
        f_stat = ms / (ss_res / df_res)
        p = stats.f.sf(f_stat, dfree, df_res)
        rec.append(dict(source=term_label(key), df=dfree, SS=ss,
                        pct_SS=100 * ss / ss_total,
                        rho=100 * np.sqrt(ss / N) / mu,
                        partial_eta2=ss / (ss + ss_res), F=f_stat, p=p,
                        order=len(key)))
    aov = pd.DataFrame(rec).sort_values("SS", ascending=False)
    aov = aov.set_index("source")
    resid_row = dict(df=df_res, SS=ss_res, pct_SS=100 * ss_res / ss_total,
                     rho=100 * np.sqrt(ss_res / N) / mu,
                     partial_eta2=np.nan, F=np.nan, p=np.nan, order=0)
    aov_out = pd.concat([aov, pd.DataFrame([resid_row], index=["Residual"])])
    _csv(aov_out, args.out, "anova_full")

    lines += [
        "VARIANCE DECOMPOSITION (5 main effects + all 10 two-way "
        "interactions; balanced full factorial, so Type I = II = III and "
        "the shares are exact)",
        f"  total SS {ss_total:.1f} over N = {N}, grand mean {mu:.4f} s, "
        f"total sd {np.sqrt(ss_total / N):.4f} s",
        "  rho = sqrt(SS/N) as a percentage of the grand mean: an ABSOLUTE",
        "  RMS effect. %SS is a share and falls when another term grows,",
        "  so the two must be read together.",
        "",
        f"  {'source':<28}{'df':>6}{'%SS':>9}{'rho%':>8}{'F':>12}{'p':>11}",
    ]
    for k, r in aov.iterrows():
        lines.append(f"  {k:<28}{int(r['df']):>6}{r['pct_SS']:>9.3f}"
                     f"{r['rho']:>8.2f}{r['F']:>12.1f}{r['p']:>11.3g}")
    lines += [f"  {'Residual':<28}{df_res:>6}{100 * ss_res / ss_total:>9.3f}"
              f"{100 * np.sqrt(ss_res / N) / mu:>8.2f}", ""]

    if args.statsmodels_check:
        import statsmodels.api as sm
        from statsmodels.formula.api import ols
        d2 = df.rename(columns={"Crossover fn": "Crossoverfn",
                                "Mutation fn": "Mutationfn"}).copy()
        d2["Pc"] = d2["Pc"].astype(str)
        d2["Pm"] = d2["Pm"].astype(str)
        terms = ["Pc", "Pm", "Selection", "Crossoverfn", "Mutationfn"]
        formula = "cost ~ " + " + ".join(
            [f"C({t})" for t in terms]
            + [f"C({a}):C({b})" for i, a in enumerate(terms)
               for b in terms[i + 1:]])
        print("  refitting with statsmodels (slow) ...")
        sm_aov = sm.stats.anova_lm(ols(formula, data=d2).fit(), typ=2)
        got = float(sm_aov.loc["Residual", "sum_sq"])
        rel = abs(got - ss_res) / ss_res
        print(f"  statsmodels residual SS {got:.4f} vs tensor {ss_res:.4f} "
              f"(rel. diff {rel:.2e})")
        assert rel < 1e-8, "tensor and statsmodels decompositions disagree"
        lines += [f"  statsmodels cross-check: residual SS agrees to "
                  f"{rel:.1e} relative", ""]

    # ---- CRN check ---------------------------------------------------
    crn = crn_block_ss(F)
    lines += [
        "COMMON RANDOM NUMBERS CHECK (run index as a blocking factor):",
        f"  SS share {crn['pct']:.2f} % of total, {crn['pct_of_within']:.2f} % "
        f"of the within-cell variation, F({crn['df']}, .) = {crn['F']:.1f}, "
        f"p = {crn['p']:.3g}",
        "  A significant run effect is EXPECTED under CRN and is what makes",
        "  run r comparable across configurations. Paired tests (Wilcoxon",
        "  signed-rank, Friedman) are therefore valid on this dataset.",
        "",
    ]
    pd.DataFrame([crn]).to_csv(os.path.join(args.out, "crn_check.csv"),
                               index=False)

    # =================================================================
    #  equivalence set vs rank 1
    # =================================================================
    # flat[k] is the run vector of configuration k. F.reshape uses C order,
    # which is exactly the order itertools.product enumerates, so the two
    # stay aligned. Every later lookup goes through this table rather than
    # through a boolean mask over the 157,500-row frame.
    flat = F.reshape(-1, runs)
    lut = {(PC[a], PM[b], SEL[c], CROSS[d], MUT[e]): k
           for k, (a, b, c, d, e) in enumerate(
               itertools.product(range(len(PC)), range(len(PM)),
                                 range(len(SEL)), range(len(CROSS)),
                                 range(len(MUT))))}
    # guard the alignment rather than trusting it
    for _chk in (0, len(flat) // 3, len(flat) - 1):
        _spec = [k for k, v in lut.items() if v == _chk][0]
        assert np.allclose(
            flat[_chk],
            F[PC.index(_spec[0]), PM.index(_spec[1]), SEL.index(_spec[2]),
              CROSS.index(_spec[3]), MUT.index(_spec[4]), :]), \
            "flat/lut misalignment"
    rows_eq = []
    for _, row in cfg.iterrows():
        spec = tuple(row[k] for k in keys)
        rr = flat[lut[spec]]
        if np.array_equal(rr, win_runs):
            p_w, p_pair = 1.0, 1.0
        else:
            p_w = stats.ttest_ind(rr, win_runs, equal_var=False).pvalue
            d = rr - win_runs
            p_pair = (1.0 if np.allclose(d, 0)
                      else stats.wilcoxon(d, zero_method="zsplit").pvalue)
        rows_eq.append(spec + (row["mean"], p_w, p_pair))
    eq = pd.DataFrame(rows_eq, columns=keys + ["mean", "p (Welch)",
                                               "p (Wilcoxon paired)"])
    eq["p_holm"] = holm(eq["p (Welch)"])
    eq["p_bh"] = benjamini_hochberg(eq["p (Welch)"])
    _csv(eq, args.out, "equivalence_set", index=False)

    tied = eq[eq["p (Welch)"] > 0.05]
    tied_pair = eq[eq["p (Wilcoxon paired)"] > 0.05]
    comp = {c: tied[c].value_counts().to_dict()
            for c in ["Selection", "Crossover fn", "Mutation fn", "Pm", "Pc"]}
    lines += [
        f"EQUIVALENCE SET vs rank 1 (uncorrected Welch, alpha = 0.05): "
        f"{len(tied)} of {n_cfg} configurations",
        f"  paired Wilcoxon (CRN-exploiting, more powerful): "
        f"{len(tied_pair)} configurations",
        f"  composition (Welch set): {comp}",
        f"  after Holm over {n_cfg - 1} comparisons, "
        f"{int((eq['p_holm'] <= 0.05).sum())} remain significantly worse; "
        f"after BH, {int((eq['p_bh'] <= 0.05).sum())}",
        "  -> the top of the ranking is a REGION, not a point.",
        "",
    ]

    # =================================================================
    #  the recommended block
    # =================================================================
    mblock = (cfg["Selection"] == BLOCK["Selection"])
    mblock &= (cfg["Crossover fn"] == BLOCK["Crossover fn"])
    mblock &= (cfg["Mutation fn"] == BLOCK["Mutation fn"])
    mblock &= cfg["Pc"].isin(BLOCK["Pc"])
    mblock &= cfg["Pm"].isin(BLOCK["Pm"])
    blk = cfg[mblock].copy()
    blk_specs = [tuple(r[k] for k in keys) for _, r in blk.iterrows()]
    if len(blk) != len(BLOCK["Pc"]) * len(BLOCK["Pm"]):
        raise SystemExit(f"recommended block matched {len(blk)} cells, "
                         f"expected {len(BLOCK['Pc']) * len(BLOCK['Pm'])}")
    blk_runs = np.concatenate([flat[lut[s]] for s in blk_specs])
    p_welch_of = dict(zip(zip(*[eq[k] for k in keys]), eq["p (Welch)"]))
    blk_in_eq = sum(1 for s in blk_specs if p_welch_of[s] > 0.05)
    _csv(blk, args.out, "recommended_block")

    pt_row = cfg[(cfg["Pc"] == POINT[0]) & (cfg["Pm"] == POINT[1])
                 & (cfg["Selection"] == POINT[2])
                 & (cfg["Crossover fn"] == POINT[3])
                 & (cfg["Mutation fn"] == POINT[4])].iloc[0]
    pt_runs = flat[lut[POINT]]
    p_pt_welch = stats.ttest_ind(pt_runs, win_runs, equal_var=False).pvalue
    p_pt_pair = (1.0 if np.array_equal(pt_runs, win_runs)
                 else stats.wilcoxon(pt_runs - win_runs,
                                     zero_method="zsplit").pvalue)

    # neighbour robustness: the worst adjacent cell in the (Pc, Pm) plane
    def neighbours(pc, pm):
        i, j = PC.index(pc), PM.index(pm)
        out = []
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            a, b = i + di, j + dj
            if 0 <= a < len(PC) and 0 <= b < len(PM):
                out.append((PC[a], PM[b]))
        return out

    def cell_mean(pc, pm, se, cr, mu_):
        return float(flat[lut[(pc, pm, se, cr, mu_)]].mean())

    nb = [cell_mean(pc, pm, *POINT[2:]) for pc, pm in neighbours(POINT[0], POINT[1])]

    lines += [
        "RECOMMENDED BLOCK (this is the recommendation; the single point "
        "below is a convenience, not a finding):",
        f"  {BLOCK['Selection']} + {BLOCK['Crossover fn']} + "
        f"{BLOCK['Mutation fn']}, Pc in {BLOCK['Pc']}, Pm in {BLOCK['Pm']}",
        f"  {len(blk)} cells x {runs} runs = {len(blk_runs)} runs, "
        f"pooled mean {blk_runs.mean():.4f} s (sd {blk_runs.std(ddof=1):.4f})",
        f"  cell means {blk['mean'].min():.4f} - {blk['mean'].max():.4f} s, "
        f"ranks {int(blk.index.min())}-{int(blk.index.max())}",
        f"  {blk_in_eq}/{len(blk)} cells inside the equivalence set",
        f"  success rate {100 * (blk_runs <= BKS + 1e-9).mean():.2f} % "
        f"vs {100 * (y <= BKS + 1e-9).mean():.2f} % over the whole grid",
        "",
        f"SINGLE POINT for readers who need one: Pc = {POINT[0]:g}, "
        f"Pm = {POINT[1]:g}, {POINT[2]} + {POINT[3]} + {POINT[4]}",
        f"  rank {int(pt_row.name)}, mean {pt_row['mean']:.4f} s, "
        f"sd {pt_row['std']:.4f}, hits {int(pt_row['hits'])}/{runs}",
        f"  vs rank 1: Welch p = {p_pt_welch:.4f}, "
        f"paired Wilcoxon p = {p_pt_pair:.4g}",
        f"  neighbour robustness: worst adjacent (Pc,Pm) cell "
        f"{max(nb):.4f} s (own mean {pt_row['mean']:.4f})",
        f"  vs the worst configuration in the grid: "
        f"{(1 - pt_row['mean'] / worst['mean']) * 100:.1f} % lower AWT",
        "",
    ]

    # =================================================================
    #  operator-conditional structure (the mechanism section)
    # =================================================================
    goodm = df["Mutation fn"].isin(GOOD_MUT)
    good, bad = df[goodm], df[~goodm]
    lines += ["Pc SLOPE DECOMPOSED BY MUTATION OPERATOR QUALITY",
              "  (MATLAB ga draws a 1-Pc share of each generation from",
              "   mutation, so Pc is also a 'how much mutation' knob.)"]
    for tag, sub in (("label-generating (%s)" % "/".join(GOOD_MUT), good),
                     ("rearrangement-only", bad)):
        gm = sub.groupby("Pc", observed=True)["cost"].mean()
        lines.append(f"  {tag:<34} " +
                     "  ".join(f"{k:g}:{v:.3f}" for k, v in gm.items()))
        lo, hi = PC[0], PC[-2] if len(PC) > 1 else PC[-1]
        lines.append(f"    slope {PC[0]:g}->{PC[-1]:g} = "
                     f"{gm.iloc[-1] - gm.iloc[0]:+.3f} s")
    lines.append("")

    pc_marg = df.groupby("Pc", observed=True)["cost"].mean()
    best_pc = pc_marg.idxmin()
    interior = PC[0] < best_pc < PC[-1]
    lines += [
        "BOUNDARY CHECK",
        "  Pc marginal  " + "  ".join(f"{k:g}:{v:.3f}"
                                      for k, v in pc_marg.items()),
        f"  -> optimum at Pc = {best_pc:g}, which is "
        f"{'INTERIOR to' if interior else 'ON THE EDGE of'} the searched grid",
    ]
    pm_marg = df.groupby("Pm", observed=True)["cost"].mean()
    lines += ["  Pm marginal  " + "  ".join(f"{k:g}:{v:.3f}"
                                            for k, v in pm_marg.items()),
              ""]

    with open(os.path.join(args.out, "stats_summary.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("  wrote stats_summary.txt")

    ctx = dict(F=F, df=df, cfg=cfg, eq=eq, marginal=marginal, aov=aov,
               aov_out=aov_out, ss_total=ss_total, ss_res=ss_res,
               df_res=df_res, mu=mu, N=N, runs=runs, n_cfg=n_cfg, BKS=BKS,
               n_pax=n_pax, PC=PC, PM=PM, SEL=SEL, CROSS=CROSS, MUT=MUT,
               FACTORS=FACTORS, meta=meta, blk=blk, blk_runs=blk_runs,
               blk_in_eq=blk_in_eq, pt_row=pt_row, best=best, worst=worst,
               flat=flat, lut=lut, crn=crn, y=y, out=args.out,
               n_pairs=n_pairs, TF=TF, PT=PT, cp=cp, lines=lines,
               p_pt_welch=p_pt_welch, p_pt_pair=p_pt_pair, term_label=term_label)
    make_tables(ctx)
    make_figures(ctx)
    print("\n" + "\n".join(lines))
    return 0


# =====================================================================
#  LaTeX tables (booktabs; acmart already loads booktabs/graphicx/amsmath)
# =====================================================================
def make_tables(c):
    out, df, cfg, eq = c["out"], c["df"], c["cfg"], c["eq"]
    PC, PM, SEL, CROSS, MUT = c["PC"], c["PM"], c["SEL"], c["CROSS"], c["MUT"]
    FACTORS, runs, n_cfg = c["FACTORS"], c["runs"], c["n_cfg"]
    BKS, y, meta, mu = c["BKS"], c["y"], c["meta"], c["mu"]
    aov, ss_res, df_res, ss_total = c["aov"], c["ss_res"], c["df_res"], c["ss_total"]
    N, term_label = c["N"], c["term_label"]
    marginal, blk, blk_runs = c["marginal"], c["blk"], c["blk_runs"]
    pt_row, best, worst = c["pt_row"], c["best"], c["worst"]
    lv = lambda vals: ", ".join(f"{v:g}" for v in vals)
    keys = ["Pc", "Pm", "Selection", "Crossover fn", "Mutation fn"]

    # ---- 1) design ---------------------------------------------------
    _tex(r"""\begin{table}[t]
\centering
\small
\caption{Factorial design of the parameter search: %d configurations, each
replicated over %d independent runs under common random numbers
(%s GA runs in total).}
\label{tab:design}
\begin{tabular}{@{}lc@{\hspace{5pt}}l@{}}
\toprule
Setting & \# & Levels\\
\midrule
Crossover rate $P_c$ & %d & %s\\
Mutation rate $P_m$ & %d & %s\\
Selection method & %d & stoch.\ uniform, roulette, tournament\\
Crossover method & %d & scattered, single point, two point\\
Mutation method & %d & uniform, block, scramble, swap, frequency\\
\bottomrule
\end{tabular}
\end{table}
""" % (n_cfg, runs, _num(int(N)), len(PC), lv(PC), len(PM), lv(PM),
       len(SEL), len(CROSS), len(MUT)), out, "design")

    _tex(r"""%% Drop-in replacement for Table~\ref{tab:design} and the sentence
%% that introduces it, for when the page budget cannot afford the float.
The parameter search enumerates a full factorial design over five settings:
the crossover rate $P_c\in\{%s\}$, the mutation rate $P_m\in\{%s\}$, three
selection methods (stochastic uniform, roulette wheel, tournament), three
crossover methods (scattered, single point, two point) and five mutation
methods (uniform, block, scramble, swap, frequency). The
$%d\times%d\times%d\times%d\times%d=%d$ resulting configurations were each
executed %d times under common random numbers, giving %s GA runs in total.
""" % (lv(PC), lv(PM), len(PC), len(PM), len(SEL), len(CROSS), len(MUT),
       n_cfg, runs, _num(int(N))), out, "design_inline")

    # ---- 2) variance decomposition -----------------------------------
    NAME = {"Pc": "$P_c$", "Pm": "$P_m$", "Selection": "Selection",
            "Crossover fn": "Crossover", "Mutation fn": "Mutation"}
    t = [r"\begin{table}[t]", r"\centering", r"\small",
         r"\caption{Variance decomposition of AWT over the $N=%s$ runs "
         r"(five main effects and all ten two-way interactions). The design is"
         % _num(int(N)),
         r"balanced, so the shares are exact and independent of the other terms.",
         r"\%SS is the share of the total sum of squares; $\rho=\sqrt{SS/N}$ is the",
         r"root-mean-square effect in seconds, given as a percentage of the grand",
         r"mean. The two answer different questions: a term's \%SS falls whenever",
         r"another term grows, while $\rho$ does not.}",
         r"\label{tab:anova}",
         r"\begin{tabular}{lrrrrr}", r"\toprule",
         r"Source & df & \%SS & $\rho$ (\%) & $\eta_p^2$ & $p$\\",
         r"\midrule"]
    for k, r in aov.iterrows():
        lab = r" $\times$ ".join(NAME.get(p.strip(), p.strip())
                                 for p in k.split(" x "))
        pv = r"$<$0.001" if r["p"] < 1e-3 else f"{r['p']:.3f}"
        t.append(f"{lab} & {int(r['df'])} & {r['pct_SS']:.2f} & "
                 f"{r['rho']:.2f} & {r['partial_eta2']:.3f} & {pv}\\\\")
    t += [r"\midrule",
          f"Residual & {int(df_res)} & {100 * ss_res / ss_total:.2f} & "
          f"{100 * np.sqrt(ss_res / N) / mu:.2f} & -- & --\\\\",
          r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    _tex("\n".join(t), out, "anova_full")

    # ---- 3) per-factor effect size + distribution-free check ---------
    rows = []
    for name, levels in FACTORS:
        groups = [df.loc[df[name] == lvl, "cost"].to_numpy() for lvl in levels]
        f_stat, p_f = stats.f_oneway(*groups)
        ss_b = sum(len(gr) * (gr.mean() - y.mean()) ** 2 for gr in groups)
        h, p_kw = stats.kruskal(*groups)
        eps_sq = (h - (len(levels) - 1)) / (len(y) - len(levels))
        rows.append((name, f_stat, p_f, ss_b / ss_total,
                     100 * np.sqrt(ss_b / N) / mu, h, p_kw, eps_sq))
    eff = pd.DataFrame(rows, columns=["factor", "F", "p (ANOVA)", "eta^2",
                                      "rho %", "H", "p (Kruskal-Wallis)",
                                      "epsilon^2"]).set_index("factor")
    eff = eff.sort_values("eta^2", ascending=False)
    _csv(eff, out, "factor_effects")

    t = [r"\begin{table}[t]", r"\centering", r"\small",
         r"\caption{Main effect of each configuration setting, on the variance",
         r"scale and on the rank scale. $\eta^2$ is the exact share of the total",
         r"sum of squares (the design is balanced), $\rho=\sqrt{SS/N}$ the",
         r"corresponding root-mean-square effect as a percentage of the grand",
         r"mean, and $\varepsilon^2$ the Kruskal--Wallis counterpart of $\eta^2$.",
         r"Every setting is significant at $p<0.001$ at this sample size, so the",
         r"informative quantity is the size, not the verdict.}",
         r"\label{tab:factor-effects}",
         r"\begin{tabular}{lrrrr}", r"\toprule",
         r"Setting & $\eta^2$ & $\rho$ (\%) & $\varepsilon^2$ & KW $H$\\",
         r"\midrule"]
    for k, r in eff.iterrows():
        t.append(f"{AXIS_TITLE[k]} & {r['eta^2']:.4f} & {r['rho %']:.2f} & "
                 f"{r['epsilon^2']:.4f} & {r['H']:.0f}\\\\")
    t += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    _tex("\n".join(t), out, "factor_effects")

    # ---- 4) marginal means with Tukey groups -------------------------
    per_lvl = {name: int(N / len(levels)) for name, levels in FACTORS}
    lo_n, hi_n = min(per_lvl.values()), max(per_lvl.values())
    t = [r"\begin{table}[t]", r"\centering", r"\small",
         r"\caption{Marginal effect of each setting on the average passenger",
         r"waiting time. Each row aggregates all runs at that level",
         r"(%s--%s runs). Success rate is the percentage of those runs that"
         % (_num(lo_n), _num(hi_n)),
         r"reached the best known AWT of %.2f\,s. Levels that do not share a" % BKS,
         r"letter differ significantly (Tukey HSD, $\alpha=0.05$); \emph{a} marks",
         r"the best group.}",
         r"\label{tab:main-effects}",
         r"\begin{tabular}{@{}lrrrc@{}}", r"\toprule",
         r"Level & Mean (s) & SD (s) & Succ.\ (\%) & Grp\\", r"\midrule"]
    prev = None
    for _, r in marginal.iterrows():
        if r["factor"] != prev:
            if prev is not None:
                t.append(r"\addlinespace")
            t.append(r"\multicolumn{5}{@{}l}{\itshape %s}\\"
                     % AXIS_TITLE[r["factor"]])
        lab = (f"{r['level']:g}" if r["factor"] in ("Pc", "Pm")
               else PRETTY[r["level"]])
        t.append(f"{lab} & {r['mean']:.3f} & {r['std']:.3f} & "
                 f"{r['success %']:.1f} & {r['group']}\\\\")
        prev = r["factor"]
    t += [r"\midrule",
          r"All %s runs & %.3f & %.3f & %.1f & \\"
          % (_num(int(N)), y.mean(), y.std(ddof=1),
             (y <= BKS + 1e-9).mean() * 100),
          r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    _tex("\n".join(t), out, "marginal_means")

    # ---- 5) best / worst configurations ------------------------------
    N_BEST, N_WORST = 10, 5
    eqi = eq.set_index(keys)
    t = [r"\begin{table*}[t]", r"\centering", r"\small",
         r"\caption{The %d best and %d worst configurations out of %d, ranked by"
         % (N_BEST, N_WORST, n_cfg),
         r"mean AWT over %d runs. ``Hits'' counts the runs that reached the best" % runs,
         r"known AWT of %.2f\,s. $p$ is a paired Wilcoxon signed-rank test against" % BKS,
         r"the rank-1 configuration, which the common random numbers make valid:",
         r"run $r$ is the same seed in every row. This table reports the extremes",
         r"of the ranking; it is not the recommendation, which is the block in",
         r"Table~\ref{tab:recommended}.}",
         r"\label{tab:best-worst}",
         r"\begin{tabular}{rccllrrrrrr}", r"\toprule",
         r"Rank & $P_c$ & $P_m$ & Selection & Crossover & Mutation & "
         r"Mean (s) & SD (s) & Min (s) & Hits & $p$\\", r"\midrule"]

    def cfg_line(i):
        r = cfg.loc[i]
        spec = tuple(r[k] for k in keys)
        pv = float(eqi.loc[spec, "p (Wilcoxon paired)"])
        ps_ = "--" if i == 1 else (r"$<$0.001" if pv < 1e-3 else f"{pv:.3f}")
        return (f"{i} & {r['Pc']:g} & {r['Pm']:g} & {PRETTY[r['Selection']]} & "
                f"{PRETTY[r['Crossover fn']]} & {PRETTY[r['Mutation fn']]} & "
                f"{r['mean']:.3f} & {r['std']:.3f} & {r['min']:.2f} & "
                f"{int(r['hits'])} & {ps_}\\\\")

    for i in range(1, N_BEST + 1):
        t.append(cfg_line(i))
    t += [r"\addlinespace", r"\multicolumn{11}{c}{$\vdots$}\\", r"\addlinespace"]
    for i in range(n_cfg - N_WORST + 1, n_cfg + 1):
        t.append(cfg_line(i))
    t += [r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""]
    _tex("\n".join(t), out, "best_worst_configurations")

    # ---- 6) the recommendation: a block, plus one interior point -----
    # Single-column float: the acmart[sigconf] column is 241.15 pt, so the
    # row labels are kept short and the qualifying detail lives in the
    # caption. At \small the same content overruns the column by 33 pt.
    ref = best["mean"]
    t = [r"\begin{table}[t]", r"\centering", r"\footnotesize",
         r"\setlength{\tabcolsep}{3.5pt}",
         r"\caption{The recommendation is the block in the upper part of the",
         r"table: tournament selection, scattered crossover and frequency",
         r"mutation with $P_c\in[%g,%g]$ and $P_m\in[%g,%g]$, i.e.\ %d cells and"
         % (min(BLOCK["Pc"]), max(BLOCK["Pc"]), min(BLOCK["Pm"]),
            max(BLOCK["Pm"]), len(blk)),
         r"%s runs. The single point is listed only for readers who need one" % _num(len(blk_runs)),
         r"setting to copy; it is not a separate finding. $\Delta$ is the change",
         r"in mean AWT relative to the best observed configuration, and every row",
         r"is a point of the same factorial design --- the study defines no",
         r"external baseline and no default GA setting.}",
         r"\label{tab:recommended}",
         r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r" & Mean & SD & Succ. & $\Delta$\\",
         r" & (s) & (s) & (\%) & (\%)\\", r"\midrule",
         r"\multicolumn{5}{@{}l}{\itshape Recommended block}\\",
         f"\\quad pooled & {blk_runs.mean():.3f} & "
         f"{blk_runs.std(ddof=1):.3f} & "
         f"{100 * (blk_runs <= BKS + 1e-9).mean():.1f} & "
         f"{(blk_runs.mean() / ref - 1) * 100:+.1f}\\\\",
         f"\\quad best cell & {blk['mean'].min():.3f} & "
         f"{blk.loc[blk['mean'].idxmin(), 'std']:.3f} & "
         f"{blk.loc[blk['mean'].idxmin(), 'success %']:.1f} & "
         f"{(blk['mean'].min() / ref - 1) * 100:+.1f}\\\\",
         f"\\quad worst cell & {blk['mean'].max():.3f} & "
         f"{blk.loc[blk['mean'].idxmax(), 'std']:.3f} & "
         f"{blk.loc[blk['mean'].idxmax(), 'success %']:.1f} & "
         f"{(blk['mean'].max() / ref - 1) * 100:+.1f}\\\\",
         r"\addlinespace",
         r"\multicolumn{5}{@{}l}{\itshape Single point, and the grid extremes}\\"]
    for label, r in [
            (r"\quad $P_c=%g$, $P_m=%g$ (rk.\ %d)"
             % (POINT[0], POINT[1], int(pt_row.name)), pt_row),
            (r"\quad best observed (rk.\ 1)", best),
            (r"\quad worst observed (rk.\ %d)" % n_cfg, worst)]:
        t.append(f"{label} & {r['mean']:.3f} & {r['std']:.3f} & "
                 f"{r['success %']:.1f} & {(r['mean'] / ref - 1) * 100:+.1f}\\\\")
    t += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    _tex("\n".join(t), out, "recommended")


# =====================================================================
#  figures
# =====================================================================
def make_figures(c):
    out, df, cfg = c["out"], c["df"], c["cfg"]
    PC, PM, SEL, CROSS, MUT = c["PC"], c["PM"], c["SEL"], c["CROSS"], c["MUT"]
    FACTORS, runs, BKS = c["FACTORS"], c["runs"], c["BKS"]
    marginal, y = c["marginal"], c["y"]
    flat, lut = c["flat"], c["lut"]
    keys = ["Pc", "Pm", "Selection", "Crossover fn", "Mutation fn"]

    # ---- 1) distribution + marginal mean per level --------------------
    fig, axes = two_row_axes((FULL_W, 4.6), len(PC), len(PM))
    for ax, (name, levels) in zip(axes, FACTORS):
        data = [df.loc[df[name] == lvl, "cost"].to_numpy() for lvl in levels]
        ax.axhline(BKS, color=ORANGE, lw=0.9, ls=(0, (4, 2)), zorder=1)
        bp = ax.boxplot(data, widths=0.6, patch_artist=True,
                        medianprops=dict(color=INK, lw=1.1),
                        whiskerprops=dict(color=AXIS, lw=0.8),
                        capprops=dict(color=AXIS, lw=0.8),
                        flierprops=dict(marker="o", ms=1.2, mfc="#b9b8b3",
                                        mec="none", alpha=0.30))
        for b in bp["boxes"]:
            b.set_facecolor(BOX_FILL)
            b.set_edgecolor(CAT5[0])
            b.set_linewidth(0.9)
        mm = marginal[marginal["factor"] == name]
        x = np.arange(1, len(levels) + 1)
        if name in ("Pc", "Pm"):
            ax.plot(x, mm["mean"], color=ORANGE, lw=1.1, zorder=4, alpha=0.85)
        ax.plot(x, mm["mean"], ls="none", marker="D", ms=3.4, color=ORANGE,
                mec="white", mew=0.6, zorder=5)
        # With seven Pc levels there is no horizontal room beside the
        # diamond, so the value goes above it on a white pad instead.
        for xi, v in zip(x, mm["mean"]):
            ax.annotate(f"{v:.2f}", (xi, v), textcoords="offset points",
                        xytext=(0, 6.5), ha="center", va="bottom",
                        fontsize=5.8, color=INK2, zorder=6,
                        bbox=dict(fc="white", ec="none", alpha=0.72, pad=0.7))
        lab, rot, ha = tick_labels(name, levels)
        ax.set_xticks(x)
        ax.set_xticklabels(lab, rotation=rot, ha=ha)
        ax.set_title(AXIS_TITLE[name], pad=4)
        ax.set_xlim(0.45, len(levels) + 0.95)
        ax.grid(axis="y")
    lo, hi = nice_limits([y.min(), np.percentile(y, 99.7)], pad=0.04)
    axes[0].set_ylim(lo, hi)
    axes[0].set_ylabel("AWT (s)")
    axes[2].set_ylabel("AWT (s)")
    n_clip = int((y > hi).sum())
    axes[0].text(0.985, 0.975, f"best known {BKS:.2f} s",
                 transform=axes[0].transAxes, fontsize=6.5, color=ORANGE,
                 ha="right", va="top")
    axes[0].text(0.985, 0.905, "diamond = mean",
                 transform=axes[0].transAxes, fontsize=6.5, color=ORANGE,
                 ha="right", va="top")
    if n_clip:
        fig.text(0.995, -0.02,
                 f"{n_clip} of {len(y)} runs ({100 * n_clip / len(y):.1f} %) "
                 f"lie above {hi:.1f} s and are outside the plotted window",
                 fontsize=5.8, color=MUTED, ha="right", va="top")
    _save(fig, out, "fig_factor_distributions")

    # ---- 2) selection x crossover heat map ---------------------------
    fig, ax = plt.subplots(figsize=(COL_W, 2.35))
    M = (df.pivot_table(index="Selection", columns="Crossover fn",
                        values="cost", observed=True)
         .reindex(index=SEL, columns=CROSS))
    im = ax.pcolormesh(np.arange(len(CROSS) + 1) - 0.5,
                       np.arange(len(SEL) + 1) - 0.5, M.values, cmap=SEQ,
                       edgecolors="white", linewidth=1.6)
    ax.invert_yaxis()
    ax.set_xlim(-0.5, len(CROSS) - 0.5)
    ax.set_ylim(len(SEL) - 0.5, -0.5)
    ax.set_xticks(range(len(CROSS)))
    ax.set_xticklabels([SHORT[v] for v in CROSS])
    ax.set_yticks(range(len(SEL)))
    ax.set_yticklabels([SHORT[v] for v in SEL])
    ax.set_xlabel("Crossover method")
    ax.set_ylabel("Selection method")
    ax.grid(False)
    lo_, hi_ = M.values.min(), M.values.max()
    bi, bj = np.unravel_index(np.argmin(M.values), M.shape)
    for (i, j), v in np.ndenumerate(M.values):
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                color="white" if (v - lo_) / (hi_ - lo_) > 0.55 else INK,
                fontweight="bold" if (i, j) == (bi, bj) else "normal")
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    cb.set_label("Mean AWT (s)", fontsize=7.5)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7)
    _save(fig, out, "fig_sel_cross_heatmap")

    # ---- 3) mutation method x {Pc, selection, crossover} -------------
    fig, axes = plt.subplots(1, 3, figsize=(FULL_W, 2.7),
                             gridspec_kw=dict(wspace=0.30,
                                              width_ratios=[len(PC), 3, 3]))
    mats = []
    for name, levels in [("Pc", PC), ("Selection", SEL),
                         ("Crossover fn", CROSS)]:
        mats.append(df.pivot_table(index=name, columns="Mutation fn",
                                   values="cost", observed=True)
                    .reindex(index=levels, columns=MUT))
    ylo, yhi = nice_limits(np.concatenate([m.values.ravel() for m in mats]),
                           pad=0.07)
    for ax, P, (name, levels) in zip(
            axes, mats, [("Pc", PC), ("Selection", SEL),
                         ("Crossover fn", CROSS)]):
        x = np.arange(len(levels))
        for k, mu_ in enumerate(MUT):
            ax.plot(x, P[mu_].to_numpy(), color=CAT5[k], marker=MARKERS[k],
                    ms=4.0, lw=1.6, ls=LINESTYLES[k], mec="white", mew=0.6,
                    label=PRETTY[mu_], zorder=3)
        lab, rot, ha = tick_labels(name, levels)
        ax.set_xticks(x)
        ax.set_xticklabels(lab, rotation=rot, ha=ha)
        ax.set_title(AXIS_TITLE[name], pad=4)
        ax.set_xlim(-0.35, len(levels) - 0.65)
        ax.set_ylim(ylo, yhi)
        ax.grid(axis="y")
        if name != "Pc":
            plt.setp(ax.get_yticklabels(), visible=False)
    axes[0].set_ylabel("Mean AWT (s)")
    h, lg = axes[0].get_legend_handles_labels()
    fig.legend(h, lg, loc="upper center", bbox_to_anchor=(0.5, 1.10), ncol=5,
               columnspacing=1.4, handlelength=2.4)
    _save(fig, out, "fig_interactions")

    # ---- 4) individual runs of the ten leading configurations --------
    # Box plots are useless here: the costs take few discrete values, so a
    # handful of stray runs stretches the axis and flattens every box. A
    # clipped strip plot with the mean and its 95 % CI shows the structure
    # and states how many runs fall outside the window.
    top = [tuple(cfg.loc[i][k] for k in keys) for i in range(1, 11)]
    allr = np.concatenate([flat[lut[s]] for s in top])
    XHI = float(np.percentile(allr, 97))
    XLO = float(allr.min()) - 0.02 * (XHI - allr.min())
    fig, ax = plt.subplots(figsize=(FULL_W, 3.2))
    rng_jit = np.random.default_rng(0)
    ylabels = []
    ax.axvline(BKS, color=ORANGE, lw=0.9, ls=(0, (4, 2)), zorder=1)
    for pos, i_ in enumerate(range(10, 0, -1)):
        r = cfg.loc[i_]
        rr = flat[lut[tuple(r[k] for k in keys)]]
        inside = rr[rr <= XHI]
        n_out = int((rr > XHI).sum())
        jit = rng_jit.uniform(-0.19, 0.19, size=len(inside))
        ax.scatter(inside, pos + jit, s=6, color=CAT5[0], alpha=0.45,
                   linewidths=0, zorder=3)
        m = rr.mean()
        ci = 1.96 * rr.std(ddof=1) / np.sqrt(len(rr))
        ax.errorbar(m, pos, xerr=ci, fmt="D", ms=4.0, color=INK,
                    ecolor=INK2, elinewidth=1.0, capsize=2.2, zorder=4)
        if n_out:
            ax.annotate(f"+{n_out} run{'s' if n_out > 1 else ''} "
                        f"to {rr.max():.2f}", (XHI, pos), xytext=(-3, 0),
                        textcoords="offset points", ha="right", va="center",
                        fontsize=6.0, color=MUTED,
                        bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.8),
                        zorder=6)
        ylabels.append(f"{i_}.  {r['Pc']:g} / {r['Pm']:g} / "
                       f"{SHORT[r['Selection']]} / {SHORT[r['Crossover fn']]}"
                       f" / {PRETTY[r['Mutation fn']]}")
    ax.set_yticks(range(10))
    ax.set_yticklabels(ylabels, fontsize=6.8)
    ax.set_ylim(-0.6, 9.6)
    ax.set_xlim(XLO, XHI)
    ax.set_xlabel(f"AWT of each of the {runs} runs (s)")
    ax.set_title("Rank / $P_c$ / $P_m$ / selection / crossover / mutation"
                 "   —   dots are individual runs, "
                 "diamond is the mean $\\pm$ 95 % CI",
                 pad=5, fontsize=7.6, loc="left")
    ax.grid(axis="x")
    ax.annotate(f"best known {BKS:.2f} s", (BKS, 9.35), xytext=(4, 0),
                textcoords="offset points", fontsize=6.6, color=ORANGE,
                va="center", zorder=6,
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.8))
    _save(fig, out, "fig_top10_runs")

    # ---- 5) rate grid under the winning operator set -----------------
    fig, axes = plt.subplots(1, 2, figsize=(FULL_W, 2.9),
                             gridspec_kw=dict(wspace=0.28))
    ts = df[(df["Selection"] == "tournament")
            & (df["Crossover fn"] == "scattered")]
    panels = [(m, f"Tournament + scattered + {PRETTY[m].lower()}")
              for m in GOOD_MUT]
    mats = [ts[ts["Mutation fn"] == m]
            .pivot_table(index="Pc", columns="Pm", values="cost",
                         observed=True).reindex(index=PC, columns=PM)
            for m, _ in panels]
    vmin = min(m.values.min() for m in mats)
    vmax = max(m.values.max() for m in mats)
    for ax, M, (_, title) in zip(axes, mats, panels):
        im = ax.pcolormesh(np.arange(len(PM) + 1) - 0.5,
                           np.arange(len(PC) + 1) - 0.5, M.values, cmap=SEQ,
                           vmin=vmin, vmax=vmax, edgecolors="white",
                           linewidth=1.6)
        ax.invert_yaxis()
        ax.set_xlim(-0.5, len(PM) - 0.5)
        ax.set_ylim(len(PC) - 0.5, -0.5)
        ax.set_xticks(range(len(PM)))
        ax.set_xticklabels([f"{v:g}" for v in PM])
        ax.set_yticks(range(len(PC)))
        ax.set_yticklabels([f"{v:g}" for v in PC])
        ax.set_xlabel(AXIS_TITLE["Pm"])
        ax.set_ylabel(AXIS_TITLE["Pc"])
        ax.set_title(f"{title}\nspread {M.values.max() - M.values.min():.2f} s",
                     pad=5, fontsize=8)
        ax.grid(False)
        bi, bj = np.unravel_index(np.argmin(M.values), M.shape)
        for (i_, j_), v in np.ndenumerate(M.values):
            ax.text(j_, i_, f"{v:.2f}", ha="center", va="center", fontsize=6.2,
                    color="white" if (v - vmin) / (vmax - vmin) > 0.55 else INK,
                    fontweight="bold" if (i_, j_) == (bi, bj) else "normal")
        for sp in ax.spines.values():
            sp.set_visible(False)
    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label("Mean AWT (s)", fontsize=8)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7)
    _save(fig, out, "fig_rate_grid")


if __name__ == "__main__":
    sys.exit(main())
