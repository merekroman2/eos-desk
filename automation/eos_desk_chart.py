#!/usr/bin/env python3
"""
eos_desk_chart.py — rebuild the six-panel "EOS Estimates vs. Henry Hub" page
from Jozef's EOSw.xlsx (the layout John runs in The Desk).

Reads only what is in the workbook (sheet "EOS"); nothing is estimated or filled.

    Fall <Y>  (orange banner)   |  Spring <Y+1>  (green banner)
    EOS bars vs HH spot         |  EOS bars vs HH spot
    EOS bars vs HH futures      |  EOS bars vs HH futures
    Fall EOS vs prompt futures  |  Spring EOS vs prompt futures   (scatter + exp trendline)

Usage:
    python eos_desk_chart.py                                  # Data/EOSw.xlsx -> Presentation/
    python eos_desk_chart.py --workbook /path/EOSw.xlsx --out /path/out
    python eos_desk_chart.py --fall 2026                      # pin the fall season (default: latest)

Outputs (in --out):
    eos_desk_<asof>_reference.png   six-panel page, fully labelled (matches The Desk)
    eos_desk_<asof>_clean.png       same page, no titles/legends/axis labels (Adobe Express layer)
    eos_desk_<asof>_data.csv        the rows that fed the charts
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import openpyxl
import pandas as pd
from matplotlib.ticker import FuncFormatter, MaxNLocator

# ---------------------------------------------------------------------------
# Paths (same convention as the other automation/ scripts)
# ---------------------------------------------------------------------------
# project root: $MR_HOME if set, else the folder above automation/
HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))
DEFAULT_WB = HOME / "Data" / "EOSw.xlsx"
DEFAULT_OUT = HOME / "Presentation"
DEFAULT_PRICES = HOME / "Data" / "eia_prices.csv"     # written by eia_pull.py --save

# ---------------------------------------------------------------------------
# Colours (Excel defaults John's page uses; EIA palette where it overlaps)
# ---------------------------------------------------------------------------
ORANGE = "#ED7D31"      # EOS bars, fall banner, trendline
BLUE = "#5B9BD5"        # HH spot / futures line
GREEN_BANNER = "#C5E0B4"
GREY_TXT = "#595959"
SEASON_COLOURS = {       # by position within the five seasons shown, oldest -> newest
    "fall":   ["#A5A5A5", "#5B9BD5", "#A9D18E", "#7030A0", "#ED7D31"],
    "spring": ["#A5A5A5", "#A9D18E", "#5B9BD5", "#F4B183", "#C00000"],
}
MARKER_RED = "#FF0000"

# ---------------------------------------------------------------------------
# Workbook reader
# ---------------------------------------------------------------------------
HEADER_ROW = 1
DATA_START = 6


def read_eos_sheet(path: Path) -> tuple[pd.DataFrame, dict[str, str], str]:
    """Return (long dataframe, season->column map, latest-week label).

    Columns in the sheet:  A date | B spot | C futures | F..M one column per season
    ('EOS Spring 2027', '  EOS Fall 2026', ...) | N all-spring | O all-fall | P/Q latest week.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if "EOS" not in wb.sheetnames:
        sys.exit(f"Sheet 'EOS' not found in {path}")
    ws = wb["EOS"]
    rows = list(ws.iter_rows(min_row=1, max_col=17, values_only=True))  # A..Q
    wb.close()

    headers = rows[HEADER_ROW - 1]
    latest_label = rows[1][15] or rows[1][16]          # P2 / Q2, e.g. "EOS 11/02/26"

    season_cols: dict[str, int] = {}
    for idx, h in enumerate(headers):
        if isinstance(h, str):
            m = re.match(r"\s*EOS (Fall|Spring) (\d{4})\s*$", h)
            if m:
                season_cols[f"{m.group(1)} {m.group(2)}"] = idx

    recs = []
    for r in rows[DATA_START - 1:]:
        d = r[0]
        if not isinstance(d, (datetime, date)):
            continue
        rec = {
            "date": pd.Timestamp(d),
            "spot": r[1],
            "futures": r[2],
            "spring_all": r[13],   # N
            "fall_all": r[14],     # O
            "latest_fall": r[15],  # P
            "latest_spring": r[16],  # Q
        }
        for s, idx in season_cols.items():
            rec[s] = r[idx]
        recs.append(rec)
    df = pd.DataFrame(recs)
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, season_cols, latest_label


def read_chart_axes(path: Path, season_cols: dict[str, int]) -> dict:
    """Pull the y-axis ranges Jozef set on his bar/line charts, keyed by
    (season, 'B'|'C') -> ((bar_min, bar_max), (line_min, line_max)).
    Returns {} if the charts can't be read; callers fall back to auto-scaling."""
    from openpyxl.utils import get_column_letter
    out = {}
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb["EOS"]
        col_to_season = {get_column_letter(i + 1): s for s, i in season_cols.items()}
        for ch in ws._charts:
            subs = getattr(ch, "_charts", [])
            if len(subs) != 2:
                continue
            bar, line = subs
            if type(bar).__name__ != "BarChart" or type(line).__name__ != "LineChart":
                continue
            bcol = re.search(r"\$([A-Z]+)\$", bar.series[0].val.numRef.f).group(1)
            lcol = re.search(r"\$([A-Z]+)\$", line.series[0].val.numRef.f).group(1)
            if bcol in col_to_season and lcol in ("B", "C"):
                bs, ls = bar.y_axis.scaling, line.y_axis.scaling
                if None not in (bs.min, bs.max, ls.min, ls.max):
                    out[(col_to_season[bcol], lcol)] = ((bs.min, bs.max), (ls.min, ls.max))
    except Exception as e:  # noqa: BLE001
        print(f"  (could not read chart axis ranges: {e}; auto-scaling)")
    return out


def weekly_prices(prices_csv: Path) -> pd.DataFrame:
    """Weekly (week-ending-Friday) Mon–Fri averages of eia_pull.py's daily series.

    HH_fut1 = Yahoo NG=F front-month close (same construction as Jozef's HH Futures:
    average of the week's daily prompt settlements).  HH_spot = EIA RNGWHHD daily spot.
    Weeks with fewer than 3 trading days are dropped rather than averaged.
    """
    d = pd.read_csv(prices_csv)
    dcol = next(c for c in d.columns if c.lower() in ("date", "day", "period"))
    d[dcol] = pd.to_datetime(d[dcol])
    d = d.set_index(dcol).sort_index()
    keep = {"HH_fut1": "futures", "HH_spot": "spot"}
    missing = [c for c in keep if c not in d.columns]
    if missing:
        sys.exit(f"{prices_csv} is missing columns {missing}")
    d = d[list(keep)].rename(columns=keep)
    d = d[d.index.dayofweek < 5]
    wk = d.resample("W-FRI")
    out = wk.mean()
    n = wk.count()
    out[n < 3] = np.nan
    return out.dropna(how="all").reset_index().rename(columns={dcol: "date"})


def merge_prices(df: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    """Use our weekly prices wherever we have them; keep Jozef's only for weeks we don't.
    Prints how the two agree where they overlap so a bad pull is visible in the log."""
    m = df.merge(weekly, on="date", how="left", suffixes=("_wb", ""))
    for col in ("spot", "futures"):
        both = m[col].notna() & m[f"{col}_wb"].notna()
        if both.any():
            diff = (m.loc[both, col] - m.loc[both, f"{col}_wb"]).abs()
            print(f"  {col:8s}: {both.sum()} overlapping weeks, median |diff| {diff.median():.3f}, "
                  f"max {diff.max():.3f} ({m.loc[diff.idxmax(), 'date'].date()})")
        src_ours = m[col].notna()
        m[col] = m[col].where(src_ours, m[f"{col}_wb"])
        print(f"  {col:8s}: {src_ours.sum()} weeks from eia_prices.csv, "
              f"{(~src_ours & m[col].notna()).sum()} weeks kept from the workbook")
        m = m.drop(columns=f"{col}_wb")
    return m


def label_seasons(df: pd.DataFrame, kind: str) -> pd.Series:
    """Season label for every row of the combined column (fall_all / spring_all).

    Dedicated season columns win; rows that only exist in the combined column
    (Fall 2022, Spring 2023 in this workbook) are labelled by calendar rule.
    """
    combined = "fall_all" if kind == "Fall" else "spring_all"
    lab = pd.Series(pd.NA, index=df.index, dtype="object")
    ded = [c for c in df.columns if c.startswith(kind + " ")]
    for c in ded:
        lab[df[c].notna()] = c
    missing = lab.isna() & df[combined].notna()
    if kind == "Fall":   # estimates for Fall Y are made Dec(Y-1) .. Nov(Y)
        yr = df["date"].dt.year + (df["date"].dt.month >= 12).astype(int)
    else:                # estimates for Spring Y are made Jul(Y-1) .. Apr(Y)
        yr = df["date"].dt.year + (df["date"].dt.month >= 7).astype(int)
    lab[missing] = kind + " " + yr[missing].astype(str)
    return lab


def exp_trend(x: np.ndarray, y: np.ndarray):
    """Excel 'Exponential' trendline: y = a·exp(b·x), fit by OLS on ln(y)."""
    m = np.isfinite(x) & np.isfinite(y) & (y > 0)
    b, lna = np.polyfit(x[m], np.log(y[m]), 1)
    return float(np.exp(lna)), float(b)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------
def _style_axes(ax):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0, colors=GREY_TXT)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8)


def bar_vs_line(ax, df, season_col, price_col, season_name, xlim, ylim,
                clean, price_label, ylim_right=None):
    sub = df[df[season_col].notna()]
    ax.bar(sub["date"], sub[season_col], width=4.5, color=ORANGE, label=f"EOS {season_name}")
    ax.set_ylim(*ylim)
    ax.set_xlim(*xlim)
    _style_axes(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=9, steps=[1, 2, 5]))
    ax.tick_params(axis="y", colors=ORANGE)

    ax2 = ax.twinx()
    px = df[(df["date"] >= xlim[0]) & (df["date"] <= xlim[1]) & df[price_col].notna()]
    ax2.plot(px["date"], px[price_col], color=BLUE, linewidth=2, label=price_label)
    if ylim_right:
        ax2.set_ylim(*ylim_right)
    else:
        lo, hi = px[price_col].min(), px[price_col].max()
        ax2.set_ylim(np.floor(lo) - 1, np.ceil(hi) + 1)
    for s in ("top", "right", "left", "bottom"):
        ax2.spines[s].set_visible(False)
    ax2.tick_params(length=0, colors=BLUE)
    ax2.yaxis.set_major_locator(MaxNLocator(nbins=8, steps=[1, 2, 5]))

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-m/%-d/%Y"))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)

    if clean:
        ax.set_xticklabels([]); ax.set_yticklabels([]); ax2.set_yticklabels([])
        return
    ax.set_title(f"EOS Estimates vs. {price_label}", fontsize=13, color=GREY_TXT, pad=10)
    ax.text(-0.02, 1.07, "Bcf", transform=ax.transAxes, color=ORANGE, fontsize=11)
    ax.text(1.02, 1.07, "$/MMBtu", transform=ax.transAxes, color=BLUE, fontsize=11, ha="right")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", ncol=2, frameon=False, fontsize=9,
              bbox_to_anchor=(0.5, 0.98))


def scatter_panel(ax, df, kind, seasons, latest_col, latest_label, trend_mask,
                  xlim, clean, ylim=None):
    labels = label_seasons(df, kind)
    combined = "fall_all" if kind == "Fall" else "spring_all"

    # trendline on the full history Jozef's chart uses (all rows in combined column)
    x_all = df.loc[trend_mask, combined].to_numpy(float)
    y_all = df.loc[trend_mask, "futures"].to_numpy(float)
    a, b = exp_trend(x_all, y_all)
    xs = np.linspace(xlim[0], xlim[1], 200)
    ax.plot(xs, a * np.exp(b * xs), linestyle=(0, (1.5, 2)), color=ORANGE, linewidth=1.6, zorder=1)

    colours = SEASON_COLOURS[kind.lower()]
    for i, s in enumerate(seasons):
        m = (labels == s) & df["futures"].notna()
        short = s.replace(" 20", " ")          # "Fall 2026" -> "Fall 26"
        ax.scatter(df.loc[m, combined], df.loc[m, "futures"], s=26, color=colours[i],
                   label=short, zorder=2 + i, edgecolors="none")

    m = df[latest_col].notna() & df["futures"].notna()
    ax.scatter(df.loc[m, latest_col], df.loc[m, "futures"], s=60, marker="D",
               color=MARKER_RED, label=latest_label, zorder=10)

    ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)
    else:
        ax.set_ylim(0, None)
    ax.grid(color="#D9D9D9", linewidth=0.8)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0, colors=BLUE, labelsize=11)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))

    if clean:
        ax.set_xticklabels([]); ax.set_yticklabels([])
        return (a, b)
    ax.set_title(f"{kind} EOS vs. prompt month futures", fontsize=16, color=GREY_TXT, pad=28)
    ax.text(-0.02, 1.06, "$/MMBtu", transform=ax.transAxes, color=BLUE, fontsize=11)
    ax.set_xlabel(f"{kind} EOS Storage Estimates (Bcf)", color=GREY_TXT, fontsize=12)
    ax.legend(loc="upper center", ncol=6, frameon=True, fontsize=9, bbox_to_anchor=(0.5, 1.07),
              handletextpad=0.1, columnspacing=0.8, edgecolor="#D9D9D9")
    return (a, b)


def banner(fig, x0, width, text, colour, y=0.965):
    fig.patches.append(plt.Rectangle((x0, y), width, 0.028, transform=fig.transFigure,
                                     color=colour, zorder=1))
    fig.text(x0 + 0.02, y + 0.008, text, color="white", fontsize=16, fontweight="bold")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_page(df, season_cols, latest_label, fall_year, out: Path, clean: bool, axes_wb: dict):
    fall_s, spring_s = f"Fall {fall_year}", f"Spring {fall_year + 1}"
    for s in (fall_s, spring_s):
        if s not in df.columns:
            sys.exit(f"No column for '{s}' in the workbook (have: {sorted(season_cols)})")

    # axis windows (the same ones the workbook's charts use)
    fall_xlim = (pd.Timestamp(fall_year - 1, 11, 1), pd.Timestamp(fall_year, 11, 1))
    spring_xlim = (pd.Timestamp(fall_year, 7, 1), pd.Timestamp(fall_year + 1, 4, 1))

    def nice_ylim(series, step):
        lo, hi = series.min(), series.max()
        return (np.floor(lo / step) * step - step, np.ceil(hi / step) * step + step)

    def ranges(season, price_letter):
        hit = axes_wb.get((season, price_letter))
        if hit:
            return hit
        return nice_ylim(df[season].dropna(), 100), None

    fig = plt.figure(figsize=(16.5, 15), facecolor="white")
    gs = fig.add_gridspec(3, 2, left=0.05, right=0.96, top=0.93, bottom=0.05,
                          hspace=0.55, wspace=0.28)
    axes = [[fig.add_subplot(gs[r, c]) for c in range(2)] for r in range(3)]

    if not clean:
        banner(fig, 0.02, 0.47, fall_s.upper(), ORANGE)
        banner(fig, 0.51, 0.47, spring_s.upper(), GREEN_BANNER)

    for ax, season, pcol, letter, xlim, lab in [
        (axes[0][0], fall_s, "spot", "B", fall_xlim, "HH Spot Price"),
        (axes[1][0], fall_s, "futures", "C", fall_xlim, "HH Futures"),
        (axes[0][1], spring_s, "spot", "B", spring_xlim, "HH Spot Price"),
        (axes[1][1], spring_s, "futures", "C", spring_xlim, "HH Futures"),
    ]:
        yl, yr = ranges(season, letter)
        bar_vs_line(ax, df, season, pcol, season, xlim, yl, clean, lab, ylim_right=yr)

    # five most recent seasons of each kind, oldest first
    fall_seasons = [f"Fall {y}" for y in range(fall_year - 4, fall_year + 1)]
    spring_seasons = [f"Spring {y}" for y in range(fall_year - 3, fall_year + 2)]

    fall_trend_mask = df["fall_all"].notna() & df["futures"].notna()
    # Jozef's spring trendline is fit on seasons before the current two (N46:N199 ≈ Spring 23–25)
    spring_labels = label_seasons(df, "Spring")
    spring_trend_mask = df["spring_all"].notna() & df["futures"].notna() & \
        spring_labels.isin(spring_seasons[:3])

    fa, fb = scatter_panel(axes[2][0], df, "Fall", fall_seasons, "latest_fall", latest_label,
                           fall_trend_mask, (3200, 4200), clean, ylim=(0, 14))
    sa, sb = scatter_panel(axes[2][1], df, "Spring", spring_seasons, "latest_spring", latest_label,
                           spring_trend_mask, (1400, 2400), clean, ylim=(0, 7))

    asof = df.loc[df["latest_fall"].notna(), "date"].max()
    tag = asof.strftime("%Y%m%d") if pd.notna(asof) else datetime.now().strftime("%Y%m%d")
    suffix = "clean" if clean else "reference"
    out.mkdir(parents=True, exist_ok=True)
    fn = out / f"eos_desk_{tag}_{suffix}.png"
    fig.savefig(fn, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"  ✓ {fn.name}")
    return fn, tag, (fa, fb), (sa, sb)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbook", type=Path, default=DEFAULT_WB)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--fall", type=int, help="fall season year (default: latest in workbook)")
    ap.add_argument("--prices", type=Path, default=DEFAULT_PRICES,
                    help="daily prices from eia_pull.py (HH_fut1, HH_spot); weekly-averaged here")
    ap.add_argument("--workbook-prices", action="store_true",
                    help="ignore --prices and use the Thomson Reuters columns in the workbook")
    args = ap.parse_args()

    if not args.workbook.exists():
        sys.exit(f"Workbook not found: {args.workbook}")
    print(f"Reading {args.workbook}")
    df, season_cols, latest_label = read_eos_sheet(args.workbook)

    if not args.workbook_prices:
        if args.prices.exists():
            print(f"Prices from {args.prices} (weekly Mon–Fri averages)")
            df = merge_prices(df, weekly_prices(args.prices))
        else:
            print(f"  {args.prices} not found — using the workbook's price columns")

    fall_year = args.fall or max(int(s.split()[1]) for s in season_cols if s.startswith("Fall"))
    last_price = df.loc[df["futures"].notna(), "date"].max()
    print(f"  seasons: {', '.join(sorted(season_cols))}")
    print(f"  prices through {last_price.date()}, latest-week marker: {latest_label}")

    axes_wb = read_chart_axes(args.workbook, season_cols)
    fn_ref, tag, ftrend, strend = build_page(df, season_cols, latest_label, fall_year, args.out, False, axes_wb)
    build_page(df, season_cols, latest_label, fall_year, args.out, True, axes_wb)

    keep = ["date", "spot", "futures", f"Fall {fall_year}", f"Spring {fall_year + 1}",
            "fall_all", "spring_all", "latest_fall", "latest_spring"]
    df[keep].dropna(subset=keep[1:], how="all").to_csv(args.out / f"eos_desk_{tag}_data.csv", index=False)
    print(f"  ✓ eos_desk_{tag}_data.csv")
    print(f"  trendlines  fall: y = {ftrend[0]:.4g}·exp({ftrend[1]:.4g}·x)   "
          f"spring: y = {strend[0]:.4g}·exp({strend[1]:.4g}·x)")


if __name__ == "__main__":
    main()
