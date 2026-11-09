#!/usr/bin/env python3
"""
eos_desk_page.py — the "Nat Gas EOS Surveys +" page of The Desk, portrait, ready to drop in.

Layout (8.5 x 11 in):
    title band
    survey summary boxes (fall | spring)   — average from the weekly consensus; median, range and
                                              count come from the survey file, which this script
                                              does not have, so those rows are left blank
    FALL / SPRING banners
    EOS bars vs HH spot        (fall | spring)
    EOS bars vs HH futures     (fall | spring)
    EOS vs prompt futures scatter, with EIA STEO vintages as triangles (fall | spring)

Reads the JSON from steo_eos_page.py. Writes eos_desk_page_<asof>.png and .pdf.

Usage:
    python eos_desk_page.py                 # newest Presentation/eos_steo_*.json
    python eos_desk_page.py --json file.json --out dir
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

plt.rcParams["text.parse_math"] = False
# project root: $MR_HOME if set, else the folder above automation/
HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))

ORANGE, BLUE, GREEN, NAVY, RED = "#ED7D31", "#5B9BD5", "#C5E0B4", "#1F3864", "#FF0000"
GREY, DARK = "#595959", "#1f2328"
PAL = {"Fall": ["#A5A5A5", "#5B9BD5", "#A9D18E", "#7030A0", "#ED7D31"],
       "Spring": ["#A5A5A5", "#A9D18E", "#5B9BD5", "#F4B183", "#C00000"]}
XLIM = {"Fall": (3200, 4200), "Spring": (1400, 2400)}
YLIM = {"Fall": (0, 14), "Spring": (0, 7)}
BAR_YLIM = {("Fall", "spot"): (3600, 4000), ("Fall", "fut"): (3600, 4000),
            ("Spring", "spot"): (1100, 2300), ("Spring", "fut"): (1300, 2300)}
PX_YLIM = {("Fall", "spot"): (0, 16), ("Fall", "fut"): (2, 6),
           ("Spring", "spot"): (2, 14), ("Spring", "fut"): (2, 7)}


def bare(ax):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, labelsize=6.5, colors=GREY)
    ax.grid(axis="y", color="#D9D9D9", lw=0.6)
    ax.set_axisbelow(True)


def bars(ax, w, kind, pcol, season, fall_year):
    key = kind.lower()
    g = w[(w[key + "_season"] == season) & w[key].notna()]
    yr = fall_year if kind == "Fall" else fall_year + 1
    x0, x1 = (pd.Timestamp(yr - 1, 11, 1), pd.Timestamp(yr, 11, 1)) if kind == "Fall" else \
             (pd.Timestamp(yr - 1, 7, 1), pd.Timestamp(yr, 4, 1))
    ax.bar(g["date"], g[key], width=4.2, color=ORANGE)
    bare(ax)
    ax.set_xlim(x0, x1)
    lo, hi = BAR_YLIM[(kind, pcol)]
    lo = min(lo, np.floor(g[key].min() / 100) * 100)
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8, steps=[1, 2, 5]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.tick_params(axis="y", colors=ORANGE)
    ax2 = ax.twinx()
    px = w[(w["date"] >= x0) & (w["date"] <= x1) & w[pcol].notna()]
    ax2.plot(px["date"], px[pcol], color=BLUE, lw=1.3)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.tick_params(length=0, labelsize=6.5, colors=BLUE)
    ax2.set_ylim(*PX_YLIM[(kind, pcol)])
    ax2.yaxis.set_major_locator(MaxNLocator(nbins=8, steps=[1, 2, 5], integer=True))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-m/1/%Y"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=5.5)
    label = "HH Spot Price" if pcol == "spot" else "HH Futures"
    ax.set_title(f"EOS Estimates vs. {label}", fontsize=8.5, color=GREY, pad=14)
    ax.legend([Rectangle((0, 0), 1, 1, color=ORANGE), plt.Line2D([], [], color=BLUE, lw=1.3)],
              [f"EOS {season} (bars, left, Bcf)", f"{label} (line, right, $/MMBtu)"],
              loc="upper center", ncol=2, fontsize=5.3, frameon=False, bbox_to_anchor=(0.5, 1.12),
              handlelength=1.4, columnspacing=1.0)


def scatter(ax, w, st, kind, trend, latest_label):
    key = kind.lower()
    skey = key + "_season"
    seasons = sorted(w.loc[w[key].notna(), skey].dropna().unique(), key=lambda s: int(s.split()[1]))[-5:]
    a, b = trend
    xs = np.linspace(*XLIM[kind], 200)
    ax.plot(xs, a * np.exp(b * xs), ls=(0, (1.5, 2.5)), color=ORANGE, lw=1.1, zorder=1)
    handles = []
    for i, s in enumerate(seasons):
        g = w[(w[skey] == s) & w["fut"].notna()]
        h = ax.scatter(g[key], g["fut"], s=9, color=PAL[kind][i], edgecolors="none", zorder=3 + i,
                       label=s.replace(" 20", " "))
        handles.append(h)
    cur = seasons[-1]
    g = st[(st["season"] == cur) & st["is_forecast"] & st["hh_fut"].notna()]
    if len(g):
        handles.append(ax.scatter(g["eos_l48"], g["hh_fut"], marker="^", s=30, facecolor=PAL[kind][-1],
                                  edgecolor=DARK, lw=0.6, zorder=9, label="EIA STEO"))
    l = w[w["latest"] & w[key].notna() & w["fut"].notna()]
    handles.append(ax.scatter(l[key], l["fut"], marker="D", s=22, color=RED, zorder=10, label=latest_label))
    bare(ax)
    ax.grid(True, color="#D9D9D9", lw=0.6)
    ax.set_xlim(*XLIM[kind])
    ax.set_ylim(*YLIM[kind])
    ax.tick_params(labelsize=7.5, colors=BLUE)
    ax.tick_params(axis="x", colors=GREY)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_title(f"{kind} EOS vs. prompt month futures", fontsize=10, color=GREY, pad=26)
    ax.set_ylabel("Prompt month HH futures ($/MMBtu)", fontsize=7, color=BLUE)
    ax.set_xlabel(f"{kind} EOS Storage Estimates (Bcf)", fontsize=7, color=GREY)
    ax.legend(handles=handles, loc="upper center", ncol=4, fontsize=5.3, frameon=True,
              edgecolor="#D9D9D9", bbox_to_anchor=(0.5, 1.17), handletextpad=0.1, columnspacing=0.6)


def survey_box(fig, x, y, wd, ht, w, kind, season, asof):
    key = kind.lower()
    g = w[(w[key + "_season"] == season) & w[key].notna()].sort_values("date")
    cur, prev = g.iloc[-1], g.iloc[-2]
    fig.patches.append(Rectangle((x, y), wd, ht, transform=fig.transFigure, fc="white", ec=NAVY, lw=1))
    fig.patches.append(Rectangle((x, y + ht - 0.018), wd, 0.018, transform=fig.transFigure, fc=NAVY, ec="none"))
    fig.text(x + wd / 2, y + ht - 0.009, f"EOS Weekly NG Storage Survey for {season}", color="white",
             fontsize=8.5, fontweight="bold", ha="center", va="center")
    c1, c2, c3, c4 = x + 0.03, x + 0.20, x + 0.30, x + 0.39
    r0 = y + ht - 0.038
    fig.text(c2, r0, cur["date"].strftime("%-d-%b"), color=RED, fontsize=7, fontweight="bold", ha="center")
    fig.text(c4, r0, prev["date"].strftime("%-d-%b"), color=RED, fontsize=7, fontweight="bold", ha="center")
    fig.text(c2, r0 - 0.012, "Current Week", fontsize=6.5, fontweight="bold", ha="center")
    fig.text(c4, r0 - 0.012, "Last Week", fontsize=6.5, fontweight="bold", ha="center")
    rows = [("Average", f"{cur[key]:,.0f}", "Bcf", f"{prev[key]:,.0f}"),
            ("Median", "—", "Bcf", "—"),
            ("Range", "—", "Bcf", "—"),
            ("No. of Estimates", "—", "", "—")]
    for i, (lab, a, u, b) in enumerate(rows):
        yy = r0 - 0.027 - i * 0.012
        fig.text(c1, yy, lab, fontsize=6.5, fontweight="bold" if lab != "Range" else "normal")
        fig.text(c2, yy, a, fontsize=6.5, fontweight="bold", ha="center")
        fig.text(c3, yy, u, fontsize=6.5, fontweight="bold", ha="center")
        fig.text(c4, yy, b, fontsize=6.5, ha="center")
    fig.text(x + wd / 2, y + 0.008, "Median, range and respondent bars come from the survey file (not in the workbook).",
             fontsize=5.3, color=GREY, ha="center", style="italic")


def build(d: dict, out: Path) -> list[Path]:
    w = pd.DataFrame(d["weekly"])
    w["date"] = pd.to_datetime(w["date"])
    st = pd.DataFrame(d["steo"])
    fy = d["fall_year"]
    fall, spring = f"Fall {fy}", f"Spring {fy + 1}"
    asof = pd.Timestamp(d["asof"])

    fig = plt.figure(figsize=(8.5, 11), facecolor="white")
    # page header
    fig.text(0.06, 0.967, "4", fontsize=16, color=GREY, fontfamily="serif")
    fig.text(0.085, 0.967, "THE DESK", fontsize=11, color=GREY, fontfamily="serif", va="baseline")
    fig.add_artist(plt.Line2D([0.20, 0.94], [0.969, 0.969], color="#7DB46C", lw=1.5))
    fig.patches.append(Rectangle((0.06, 0.885), 0.88, 0.07, transform=fig.transFigure, fc=GREEN, ec="none"))
    fig.text(0.50, 0.92, "Nat Gas EOS Surveys +", fontsize=22, color="white", ha="center", va="center",
             fontfamily="monospace")
    # survey boxes
    survey_box(fig, 0.06, 0.74, 0.43, 0.13, w, "Fall", fall, asof)
    survey_box(fig, 0.51, 0.74, 0.43, 0.13, w, "Spring", spring, asof)
    # banners
    for x, txt, c in ((0.06, fall.upper(), ORANGE), (0.51, spring.upper(), GREEN)):
        fig.patches.append(Rectangle((x, 0.712), 0.43, 0.016, transform=fig.transFigure, fc=c, ec="none"))
        fig.text(x + 0.215, 0.720, txt, color="white", fontsize=9, fontweight="bold", va="center", ha="center")

    gs = fig.add_gridspec(3, 2, left=0.10, right=0.92, top=0.685, bottom=0.055, hspace=0.62, wspace=0.42,
                          height_ratios=[1, 1, 1.25])
    bars(fig.add_subplot(gs[0, 0]), w, "Fall", "spot", fall, fy)
    bars(fig.add_subplot(gs[0, 1]), w, "Spring", "spot", spring, fy)
    bars(fig.add_subplot(gs[1, 0]), w, "Fall", "fut", fall, fy)
    bars(fig.add_subplot(gs[1, 1]), w, "Spring", "fut", spring, fy)
    scatter(fig.add_subplot(gs[2, 0]), w, st, "Fall", d["trend"]["Fall"], d["latest_label"])
    scatter(fig.add_subplot(gs[2, 1]), w, st, "Spring", d["trend"]["Spring"], d["latest_label"])

    fig.text(0.06, 0.018, "Prices: Yahoo NG=F front-month and EIA Henry Hub spot, Mon–Fri weekly averages. "
             "Triangles: EIA STEO end-of-season working gas (Lower 48), one per monthly release, priced at release week.",
             fontsize=5.5, color=GREY)

    out.mkdir(parents=True, exist_ok=True)
    tag = d["asof"].replace("-", "")
    paths = [out / f"eos_desk_page_{tag}.png", out / f"eos_desk_page_{tag}.pdf"]
    for p in paths:
        fig.savefig(p, dpi=300 if p.suffix == ".png" else None, facecolor="white")
    plt.close(fig)
    return paths


def build_block(d: dict, out: Path, which: str = "both") -> list[Path]:
    """Just the banner + charts, for placing in InDesign.
    which = "both" (2x3 block, 7.5 x 7.6 in), "fall" or "spring" (one column, 3.65 x 7.6 in)."""
    w = pd.DataFrame(d["weekly"])
    w["date"] = pd.to_datetime(w["date"])
    st = pd.DataFrame(d["steo"])
    fy = d["fall_year"]
    cols = {"fall": ("Fall", f"Fall {fy}", ORANGE), "spring": ("Spring", f"Spring {fy + 1}", GREEN)}
    keys = ["fall", "spring"] if which == "both" else [which]
    ncol = len(keys)
    fig = plt.figure(figsize=(7.5 if ncol == 2 else 3.65, 7.6), facecolor="white")
    colw = 0.95 / ncol if ncol == 2 else 0.9
    gs = fig.add_gridspec(3, ncol, left=0.10 if ncol == 1 else 0.075, right=0.90 if ncol == 1 else 0.945,
                          top=0.925, bottom=0.075, hspace=0.62, wspace=0.42, height_ratios=[1, 1, 1.25])
    for j, k in enumerate(keys):
        kind, season, colour = cols[k]
        x0 = (0.02 + j * 0.495) if ncol == 2 else 0.02
        wd = 0.465 if ncol == 2 else 0.96
        fig.patches.append(Rectangle((x0, 0.965), wd, 0.025, transform=fig.transFigure, fc=colour, ec="none"))
        fig.text(x0 + wd / 2, 0.9775, season.upper(), color="white", fontsize=9, fontweight="bold", va="center", ha="center")
        bars(fig.add_subplot(gs[0, j]), w, kind, "spot", season, fy)
        bars(fig.add_subplot(gs[1, j]), w, kind, "fut", season, fy)
        scatter(fig.add_subplot(gs[2, j]), w, st, kind, d["trend"][kind], d["latest_label"])
    note = ("Prices: Yahoo NG=F front-month and EIA Henry Hub spot, Mon–Fri weekly averages. "
            "Triangles: EIA STEO end-of-season working gas (Lower 48), priced at release week.")
    if ncol == 1:
        note = note.replace("averages. ", "averages.\n")
    fig.text(0.02, 0.008, note, fontsize=5, color=GREY, va="bottom")
    out.mkdir(parents=True, exist_ok=True)
    tag = d["asof"].replace("-", "")
    name = "eos_charts_2x3" if which == "both" else f"eos_charts_{which}_column"
    paths = [out / f"{name}_{tag}.png", out / f"{name}_{tag}.pdf"]
    for pth in paths:
        fig.savefig(pth, dpi=300 if pth.suffix == ".png" else None, facecolor="white")
    plt.close(fig)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--out", type=Path, default=HOME / "Presentation")
    args = ap.parse_args()
    js = args.json or max(args.out.glob("eos_steo_*.json"), default=None)
    if not js or not js.exists():
        sys.exit("No eos_steo_<asof>.json found — run steo_eos_page.py first")
    d = json.loads(js.read_text())
    for p in build(d, args.out):
        print(f"  ✓ {p.name}")
    for which in ("both", "fall", "spring"):
        for p in build_block(d, args.out, which):
            print(f"  ✓ {p.name}")


if __name__ == "__main__":
    main()
