"""
draw_scenario.py
================
Draw one dispatch snapshot as a schematic, for the paper's method section.

The job is not to show a magnitude but to make the problem instance concrete:
where the cars are, which way they are going, who is already inside them, who
is waiting and where each waiting passenger wants to go. So the form is a
building elevation, not a chart -- floor is the axis, and everything else is
placed against it.

Encoding
    floor        vertical axis, shared by both panels
    car          filled marker at its current floor, with a direction arrow
                 and a thin stem to each in-car destination
    passenger    thin arrow from origin floor to destination floor
    direction    colour AND arrowhead, so the figure survives greyscale
                 printing and colour-vision deficiency

The two hues are the reference palette's slots 1 and 2, validated with the
palette checker: CVD separation dE 24.7 (protan) / 32.7 (tritan),
normal-vision 33.6, both above 3:1 contrast against the surface.

Usage:
    python draw_scenario.py --xlsx veri/initials_file.xlsx --label S1 \
                            --out cikti --name fig_scenario
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import openpyxl

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow

SHEET = "Sayfa1"
FIRST = 3

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e8e7e3", "#8a8a85"
UP, DOWN = "#2a78d6", "#eb6834"
CAR_FILL, CAR_EDGE = "#dfe7ef", "#52514e"
FULL_W, COL_W = 7.03, 3.35
PAD_IN = 0.01

plt.rcParams.update({
    "font.family": ["DejaVu Sans"], "font.size": 8,
    "axes.titlesize": 8.0, "axes.labelsize": 8.0,
    "xtick.labelsize": 7.0, "ytick.labelsize": 7.0, "legend.fontsize": 7.0,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.7, "axes.labelcolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK2, "ytick.color": INK2,
    "grid.color": GRID, "grid.linewidth": 0.6,
    "text.color": INK, "legend.frameon": False,
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})


def _pdf_width_pt(path):
    import re
    with open(path, "rb") as f:
        head = f.read(8192)
    m = re.search(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+"
                  rb"([-\d.]+)\s+([-\d.]+)\s*\]", head)
    return None if not m else float(m.group(3)) - float(m.group(1))


def save(fig, out, name, target_w):
    for _ in range(8):
        fig.canvas.draw()
        w = fig.get_tightbbox(fig.canvas.get_renderer()).width + 2 * PAD_IN
        if abs(w - target_w) < 0.004:
            break
        fw, fh = fig.get_size_inches()
        fig.set_size_inches(max(0.3 * target_w, fw + (target_w - w)), fh)
    pdf = os.path.join(out, f"{name}.pdf")
    fig.savefig(pdf, bbox_inches="tight", pad_inches=PAD_IN)
    for _ in range(4):
        got = _pdf_width_pt(pdf)
        if got is None or abs(got - target_w * 72) < 0.25:
            break
        fw, fh = fig.get_size_inches()
        fig.set_size_inches(fw + (target_w * 72 - got) / 72, fh)
        fig.savefig(pdf, bbox_inches="tight", pad_inches=PAD_IN)
    fig.savefig(os.path.join(out, f"{name}.png"), dpi=300,
                bbox_inches="tight", pad_inches=PAD_IN)
    plt.close(fig)
    print(f"  wrote {name}.pdf ({_pdf_width_pt(pdf):.2f} pt) / .png")


def read_snapshot(path):
    ws = openpyxl.load_workbook(path)[SHEET]
    col = lambda L: [ws[f"{L}{r}"].value for r in range(FIRST, ws.max_row + 1)]
    cl = lambda L: [v for v in col(L) if v is not None]
    return dict(
        n_floors=int(ws[f"A{FIRST}"].value), n_cars=int(ws[f"E{FIRST}"].value),
        car_floor=[int(v) for v in cl("H")],
        car_state=[int(v) for v in cl("I")],
        car_df=[[int(x) for x in str(v).split()] for v in cl("J")],
        up=list(zip([int(v) for v in cl("K")], [int(v) for v in cl("L")])),
        dn=list(zip([int(v) for v in cl("N")], [int(v) for v in cl("O")])))


def arrow(ax, x, y0, y1, colour, lw=1.0, head=0.9):
    """Thin stem with a small head, drawn in data coordinates."""
    d = np.sign(y1 - y0)
    ax.plot([x, x], [y0, y1 - d * head], color=colour, lw=lw,
            solid_capstyle="butt", zorder=3)
    ax.add_patch(FancyArrow(x, y1 - d * head, 0, d * head, width=0,
                            head_width=0.34, head_length=head,
                            length_includes_head=True, color=colour,
                            linewidth=0, zorder=3))


def main():
    ap = argparse.ArgumentParser(
        description="Draw a dispatch snapshot from an initials_file*.xlsx. "
                    "Run it from the folder holding those files and it needs "
                    "no arguments at all.")
    ap.add_argument("--xlsx", default="initials_file.xlsx",
                    help="snapshot workbook (default: initials_file.xlsx)")
    ap.add_argument("--label", default="",
                    help="name used only in the console summary")
    ap.add_argument("--out", default=".",
                    help="output folder (default: current folder)")
    ap.add_argument("--name", default=None,
                    help="output basename (default: derived from --xlsx, so "
                         "initials_file_S2.xlsx -> fig_scenario_S2)")
    ap.add_argument("--width", choices=["column", "text"], default="text",
                    help="acmart target width: text = 7.03 in (default), "
                         "column = 3.35 in (cramped with 17 passengers)")
    args = ap.parse_args()
    if not os.path.exists(args.xlsx):
        raise SystemExit(
            f"cannot find {args.xlsx!r}. Run this from the folder that holds "
            f"the initials_file*.xlsx files, or pass --xlsx <path>.")
    if args.name is None:
        stem = os.path.splitext(os.path.basename(args.xlsx))[0]
        suffix = stem[len("initials_file"):].lstrip("_") \
            if stem.startswith("initials_file") else stem
        args.name = "fig_scenario" + (f"_{suffix}" if suffix else "")
    if not args.label:
        args.label = os.path.splitext(os.path.basename(args.xlsx))[0]
    os.makedirs(args.out, exist_ok=True)
    s = read_snapshot(args.xlsx)
    NF = s["n_floors"]
    target = COL_W if args.width == "column" else FULL_W

    fig, ax = plt.subplots(figsize=(target, 3.25))

    # one shared floor axis; the horizontal direction is not a scale but
    # three labelled bands, so it carries no ticks of its own
    n = s["n_cars"]
    up = sorted(s["up"])
    dn = sorted(s["dn"], reverse=True)
    GAP = 1.6
    x_car = list(np.arange(1, n + 1))
    x_up = list(np.arange(1, len(up) + 1) + n + GAP)
    x_dn = list(np.arange(1, len(dn) + 1) + n + GAP + len(up) + GAP)
    right = x_dn[-1]

    ax.set_ylim(-1.5, NF + 3.2)
    ax.set_xlim(0.2, right + 0.8)
    ax.set_yticks([1] + list(range(5, NF + 1, 5)))
    ax.set_ylabel("Floor")
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_bounds(1, NF)

    for xb in (x_car[-1] + GAP / 2, x_up[-1] + GAP / 2):
        ax.plot([xb, xb], [0.2, NF + 0.8], color=GRID, lw=0.8, zorder=1)

    # ---- cars: one stem per in-car destination, arrowhead on the
    #      farthest one, so position and direction are a single mark -----
    for xi, f, st, ds in zip(x_car, s["car_floor"], s["car_state"],
                             s["car_df"]):
        colour = UP if st == 1 else DOWN
        far = max(ds, key=lambda d: abs(d - f))
        for d in ds:
            if d != far:
                ax.plot([xi, xi], [f, d], color=colour, lw=0.8, alpha=0.55,
                        zorder=2)
                ax.plot([xi], [d], marker="_", ms=4.6, mew=1.0, color=colour,
                        zorder=3)
        arrow(ax, xi, f, far, colour, lw=1.0, head=1.1)
        ax.plot([xi], [f], marker="s", ms=5.4, mfc=CAR_FILL, mec=CAR_EDGE,
                mew=0.9, zorder=4)
        ax.annotate(str(x_car.index(xi) + 1), (xi, -0.3), ha="center",
                    va="top", fontsize=6.4, color=INK2)

    # ---- waiting passengers -----------------------------------------
    for xs, pas, colour in ((x_up, up, UP), (x_dn, dn, DOWN)):
        for xi, (o, d) in zip(xs, pas):
            arrow(ax, xi, o, d, colour, lw=0.9, head=1.0)
            ax.plot([xi], [o], marker="o", ms=2.6, color=colour, zorder=4)

    # ---- band labels -------------------------------------------------
    def band(xs, text, colour):
        ax.text(np.mean(xs), NF + 1.6, text, ha="center", va="bottom",
                fontsize=7.2, color=colour)

    band(x_car, f"{n} cars", INK)
    band(x_up, f"{len(up)} passengers going up", UP)
    band(x_dn, f"{len(dn)} going down", DOWN)
    ax.text(np.mean(x_up + x_dn), -1.6,
            "one arrow per passenger: origin $\\rightarrow$ destination",
            ha="center", va="bottom", fontsize=6.4, color=MUTED)

    # ---- legend: three mark types, direction also carried by the head --
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="s", ms=5.4, mfc=CAR_FILL, mec=CAR_EDGE,
               mew=0.9, ls="none", label="car, at its current floor"),
        Line2D([], [], color=UP, lw=1.0, marker="^", ms=4.0,
               label="travelling up (car or passenger)"),
        Line2D([], [], color=DOWN, lw=1.0, marker="v", ms=4.0,
               label="travelling down"),
        Line2D([], [], color=INK2, lw=0.8, marker="_", ms=5.0, ls="none",
               label="in-car destination"),
    ]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.055), ncol=4, columnspacing=1.4,
              handletextpad=0.5, borderpad=0.0)

    n_calls = len(set(o for o, _ in s["up"])) + len(set(o for o, _ in s["dn"]))
    # instance counts are printed to stdout for the caption, not drawn
    note = (f"{len(s['up']) + len(s['dn'])} waiting passengers, "
            f"{n_calls} distinct hall calls, {n} cars carrying "
            f"{sum(len(d) for d in s['car_df'])} passengers")
    save(fig, args.out, args.name, target)
    print(f"  {args.label}: {note}")


if __name__ == "__main__":
    main()