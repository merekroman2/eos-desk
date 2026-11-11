#!/usr/bin/env python3
"""
eos_desk_column.py — one Desk column (3.4 in wide), three charts stacked, in The Desk's brand:

    <SEASON> ribbon
    EOS estimates vs HH spot       (bars + line)
    EOS estimates vs HH futures    (bars + line)
    EOS vs prompt-month futures    (scatter, five seasons, EIA STEO triangles, trendline)

The latest survey week is called out in every chart: its bar is outlined in ink and labelled with
an arrow, and on the scatter it is a large red diamond with a ring and an arrowed label giving the
estimate and the price.

Reads the JSON from steo_eos_page.py. Writes eos_column_<season>_<asof>.pdf/.png.

Usage:
    python eos_desk_column.py                     # fall and spring, newest Presentation/eos_steo_*.json
    python eos_desk_column.py --season fall
"""
from __future__ import annotations

import argparse
import json
import os
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desk_style as ds  # noqa: E402

HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))

# past seasons in quiet tints, current season in the EOS orange (oldest -> newest)
PAL = {"Fall": ["#C9C9C9", "#9DBFE0", "#A9D18E", "#B79FD0", ds.CHART_EOS],
       "Spring": ["#C9C9C9", "#A9D18E", "#9DBFE0", "#F4C7A3", ds.CHART_EOS]}
XLIM = {"Fall": (3200, 4200), "Spring": (1400, 2400)}
YLIM = {"Fall": (0, 14), "Spring": (0, 7)}
BAR_YLIM = {"Fall": (3600, 4000), "Spring": (1100, 2300)}
PX_YLIM = {("Fall", "spot"): (0, 16), ("Fall", "fut"): (2, 6),
           ("Spring", "spot"): (2, 14), ("Spring", "fut"): (2, 7)}
LATEST = ds.SURVEY_RED


def _frame(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(ds.INK)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.grid(axis="y", color=ds.GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=6, colors=ds.MUTED)


def _title(ax, text, pts):
    """Title a fixed distance (points) above the axes, clear of the legend row(s) under it."""
    ax.annotate(text, xy=(0, 1), xycoords="axes fraction", xytext=(-2, pts), textcoords="offset points",
                fontsize=7.5, fontweight="bold", color=ds.INK, va="bottom", ha="left")


def survey_label(d: dict, data_date: pd.Timestamp) -> str:
    """John names a survey by its Monday (e.g. 'EOS 11/02/26'); the data rows carry the week-ending Friday."""
    try:
        return "Survey " + pd.to_datetime(str(d["latest_label"]).split()[-1], format="%m/%d/%y").strftime("%b %-d")
    except (ValueError, KeyError, IndexError):
        return "Week ending " + data_date.strftime("%b %-d")


def bars(ax, w, kind, pcol, season, fall_year, latest_date, lab):
    key = kind.lower()
    g = w[(w[key + "_season"] == season) & w[key].notna()]
    yr = fall_year if kind == "Fall" else fall_year + 1
    # season window plus two weeks, so the last surveys (dated the Friday before) stay on the chart
    x0, x1 = (pd.Timestamp(yr - 1, 11, 1), pd.Timestamp(yr, 11, 15)) if kind == "Fall" else \
             (pd.Timestamp(yr - 1, 7, 1), pd.Timestamp(yr, 4, 15))
    lo, hi = BAR_YLIM[kind]
    lo = min(lo, np.floor(g[key].min() / 100) * 100)
    hi = max(hi, np.ceil((g[key].max() + 0.35 * (g[key].max() - lo)) / 100) * 100)   # room for the label
    ax.bar(g["date"], g[key] - lo, bottom=lo, width=4.2, color=ds.CHART_EOS, zorder=2)
    last = g[g["date"] == latest_date]
    if len(last):                      # latest week: ink outline + arrowed label
        r = last.iloc[0]
        ax.bar([r["date"]], [r[key] - lo], bottom=lo, width=4.2, color=ds.CHART_EOS, edgecolor=ds.INK,
               lw=1.1, zorder=4)
        ax.annotate(f"{lab}: {r[key]:,.0f} Bcf",
                    xy=(r["date"], r[key]), xytext=(r["date"] - pd.Timedelta(days=12), hi - 0.04 * (hi - lo)),
                    textcoords="data", fontsize=6, fontweight="bold", color=ds.INK, ha="right", va="top",
                    bbox=dict(boxstyle="square,pad=0.15", fc=ds.PAPER, ec="none"),
                    arrowprops=dict(arrowstyle="-|>", color=ds.INK, lw=0.8, mutation_scale=6,
                                    shrinkA=1, shrinkB=1, connectionstyle="angle,angleA=0,angleB=90,rad=0"),
                    zorder=6)
    _frame(ax)
    ax.set_xlim(x0, x1)
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.tick_params(axis="y", colors=ds.CHART_EOS)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=range(1, 13, 2)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    ax2 = ax.twinx()
    px = w[(w["date"] >= x0) & (w["date"] <= x1) & w[pcol].notna()]
    ax2.plot(px["date"], px[pcol], color=ds.CHART_HH, lw=1.4, zorder=3)
    for s in ax2.spines.values():
        s.set_visible(False)
    ax2.set_ylim(*PX_YLIM[(kind, pcol)])
    ax2.yaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5], integer=True))
    ax2.tick_params(length=0, labelsize=6, colors=ds.CHART_HH)

    label = "HH spot" if pcol == "spot" else "HH prompt futures"
    _title(ax, f"EOS estimates vs {label}", 13)
    ax.legend([Rectangle((0, 0), 1, 1, color=ds.CHART_EOS), plt.Line2D([], [], color=ds.CHART_HH, lw=1.4)],
              [f"EOS {season} (left, Bcf)", f"{label} (right, $/MMBtu)"], loc="lower left",
              bbox_to_anchor=(-0.02, 1.0), ncol=2, fontsize=5.4, frameon=False, handlelength=1.2,
              columnspacing=0.9, borderaxespad=0.1)


def scatter(ax, w, st, kind, trend, latest_date, lab):
    key = kind.lower()
    skey = key + "_season"
    seasons = sorted(w.loc[w[key].notna(), skey].dropna().unique(), key=lambda s: int(s.split()[1]))[-5:]
    a, b = trend
    xs = np.linspace(*XLIM[kind], 200)
    ax.plot(xs, a * np.exp(b * xs), ls=(0, (1.5, 2.5)), color=ds.MUTED, lw=1, zorder=1)
    handles = []
    for i, s in enumerate(seasons):
        g = w[(w[skey] == s) & w["fut"].notna()]
        cur = i == len(seasons) - 1
        handles.append(ax.scatter(g[key], g["fut"], s=12 if cur else 8, color=PAL[kind][i],
                                  edgecolors="white" if cur else "none", linewidths=0.3,
                                  zorder=4 if cur else 2, label=s.replace(" 20", " \u2019")))
    cur_s = seasons[-1]
    g = st[(st["season"] == cur_s) & st["is_forecast"] & st["hh_fut"].notna()]
    if len(g):
        handles.append(ax.scatter(g["eos_l48"], g["hh_fut"], marker="^", s=26, facecolor=ds.CHART_EOS,
                                  edgecolor=ds.INK, lw=0.6, zorder=5, label="EIA STEO"))
    r = w[(w["date"] == latest_date) & w[key].notna() & w["fut"].notna()]
    if len(r):
        r = r.iloc[0]
        ax.scatter([r[key]], [r["fut"]], s=150, facecolor="none", edgecolor=LATEST, lw=1, zorder=7)
        handles.append(ax.scatter([r[key]], [r["fut"]], marker="D", s=40, color=LATEST, edgecolor="white",
                                  lw=0.8, zorder=8, label=lab))
        x0, x1 = XLIM[kind]
        y0, y1 = YLIM[kind]
        ax.annotate(f"{lab}\n{r[key]:,.0f} Bcf at ${r['fut']:.2f}",
                    xy=(r[key], r["fut"]), xytext=(x0 + 0.60 * (x1 - x0), y0 + 0.52 * (y1 - y0)),
                    fontsize=6.3, fontweight="bold", color=LATEST, ha="center", va="bottom",
                    bbox=dict(boxstyle="square,pad=0.2", fc=ds.PAPER, ec="none"),
                    arrowprops=dict(arrowstyle="-|>", color=LATEST, lw=0.9, mutation_scale=7,
                                    shrinkA=2, shrinkB=6, connectionstyle="arc3,rad=-0.15"), zorder=9)
    _frame(ax)
    ax.grid(True, color=ds.GRID, lw=0.5)
    ax.set_xlim(*XLIM[kind])
    ax.set_ylim(*YLIM[kind])
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 5]))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel(f"{kind} EOS estimate (Bcf)", fontsize=6, color=ds.MUTED, labelpad=2)
    ax.set_ylabel("Prompt HH ($/MMBtu)", fontsize=6, color=ds.MUTED, labelpad=2)
    _title(ax, f"{kind} EOS vs prompt-month futures", 5)
    ax.legend(handles=handles, loc="upper right", ncol=2, fontsize=5.2, frameon=True, facecolor=ds.PAPER,
              edgecolor=ds.GRID, framealpha=1, handletextpad=0.2, columnspacing=0.8, borderaxespad=0.4,
              borderpad=0.4)


def build(d: dict, out: Path, which: str) -> list[Path]:
    ds.use_desk_fonts()
    w = pd.DataFrame(d["weekly"])
    w["date"] = pd.to_datetime(w["date"])
    st = pd.DataFrame(d["steo"])
    fy = d["fall_year"]
    kind = "Fall" if which == "fall" else "Spring"
    season = f"Fall {fy}" if kind == "Fall" else f"Spring {fy + 1}"
    lw = w[w["latest"] & w[kind.lower()].notna()]
    latest = lw["date"].max() if len(lw) else w.loc[w[kind.lower()].notna(), "date"].max()

    W, H = ds.COLUMN_IN, 8.4
    fig = plt.figure(figsize=(W, H), facecolor=ds.PAPER)
    ds.ribbon(fig, 0.06 / W, (H - 0.32) / H, (W - 0.12) / W, 0.22 / H, season, fontsize=8.5)
    left, right = 0.38 / W, 1 - 0.36 / W
    axes = [fig.add_axes([left, (H - 2.30) / H, right - left, 1.55 / H]),
            fig.add_axes([left, (H - 4.55) / H, right - left, 1.55 / H]),
            fig.add_axes([left, 0.62 / H, right - left, 2.80 / H])]
    lab = survey_label(d, latest)
    bars(axes[0], w, kind, "spot", season, fy, latest, lab)
    bars(axes[1], w, kind, "fut", season, fy, latest, lab)
    scatter(axes[2], w, st, kind, d["trend"][kind], latest, lab)
    fig.text(0.06 / W, 0.10 / H,
             "Survey: weekly EOS consensus. Prices: NG=F front month and EIA Henry Hub spot, Mon\u2013Fri averages.\n"
             "Triangles: EIA STEO end-of-season Lower 48 working gas, priced at release week.",
             fontsize=4.6, color=ds.MUTED, va="bottom")

    out.mkdir(parents=True, exist_ok=True)
    tag = d["asof"].replace("-", "")
    paths = [out / f"eos_column_{which}_{tag}.png", out / f"eos_column_{which}_{tag}.pdf"]
    for p in paths:
        fig.savefig(p, dpi=ds.DPI if p.suffix == ".png" else None, facecolor=ds.PAPER)
    plt.close(fig)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--out", type=Path, default=HOME / "Presentation")
    ap.add_argument("--season", choices=["fall", "spring", "both"], default="both")
    args = ap.parse_args()
    js = args.json or max(args.out.glob("eos_steo_*.json"), default=None)
    if not js or not js.exists():
        sys.exit("No eos_steo_<asof>.json found — run steo_eos_page.py first")
    d = json.loads(js.read_text())
    for which in (["fall", "spring"] if args.season == "both" else [args.season]):
        for p in build(d, args.out, which):
            print(f"  ✓ {p.name}")


if __name__ == "__main__":
    main()
