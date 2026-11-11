#!/usr/bin/env python3
"""
john_survey.py — read John's EOS survey workbook and draw his survey panels in The Desk's brand.

Workbook (e.g. "New-fall-spring-2027 11-2-2026.xlsx"): one sheet per season, named F<year> / S<year>.
    B1          current survey week (John sets this each Monday)
    row 3/4/5   5-year average / last-year / current Lower 48 storage, per survey week (typed by John)
    row 13      survey week dates from column C
    rows 14+    one row per respondent, one estimate per week (blank = no estimate that week)
fChart / sChart D5 hold the last-year end-of-season level John draws as the dashed line.

Writes (in Data/):
    eos_survey_responses.csv   survey_date, season, rid, estimate_bcf   (respondent names are NOT copied)
    eos_survey_weekly.csv      survey_date, season, n, average, median, low, high,
                               current_level, last_year_level, five_year_level
Draws (in Presentation/), one Desk column wide (3.4 in, 300 dpi), for the current week:
    eos_survey_panel_fall_<date>.pdf/.png, eos_survey_panel_spring_<date>.pdf/.png

Usage:
    python john_survey.py                                   # newest Data/*fall-spring*.xlsx
    python john_survey.py --workbook "Data/New-fall-spring-2027 11-2-2026.xlsx"
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
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import desk_style as ds  # noqa: E402

HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))
SHEET_RE = re.compile(r"^([FS])(\d{4})$")


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------
def _isdate(v):
    return isinstance(v, (datetime, date))


def read_workbook(path: Path):
    wb = openpyxl.load_workbook(path, data_only=True)
    resp, weekly, current = [], [], {}
    for ws in wb.worksheets:
        m = SHEET_RE.match(ws.title)
        if not m:
            continue
        season = ("Fall" if m.group(1) == "F" else "Spring") + " " + m.group(2)
        cols = {c: pd.Timestamp(ws.cell(13, c).value) for c in range(3, ws.max_column + 1)
                if _isdate(ws.cell(13, c).value)}
        if _isdate(ws["B1"].value):
            current[season] = pd.Timestamp(ws["B1"].value)
        for c, d in cols.items():
            vals = []
            for r in range(14, ws.max_row + 1):
                v = ws.cell(r, c).value
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                    rid = ws.cell(r, 1).value
                    resp.append(dict(survey_date=d, season=season, rid=rid, estimate_bcf=float(v)))
                    vals.append(float(v))
            lv = [ws.cell(r, c).value for r in (3, 4, 5)]
            lv = [v if isinstance(v, (int, float)) and v else None for v in lv]
            if vals or any(lv):
                s = pd.Series(vals, dtype=float)
                weekly.append(dict(survey_date=d, season=season, n=len(vals),
                                   average=s.mean() if len(s) else None, median=s.median() if len(s) else None,
                                   low=s.min() if len(s) else None, high=s.max() if len(s) else None,
                                   five_year_level=lv[0], last_year_level=lv[1], current_level=lv[2]))
    # last-year EOS line from the chart sheets (they point at the live season sheets)
    last_eos = {}
    for chart, kind in (("fChart", "Fall"), ("sChart", "Spring")):
        if chart in wb.sheetnames:
            v = wb[chart]["D5"].value
            seasons = [s for s in current if s.startswith(kind)]
            if isinstance(v, (int, float)) and seasons:
                last_eos[max(seasons, key=lambda s: int(s.split()[1]))] = float(v)
    r = pd.DataFrame(resp)
    w = pd.DataFrame(weekly).sort_values(["season", "survey_date"])
    return r, w, current, last_eos


def check_levels(w: pd.DataFrame, current: dict) -> list[str]:
    """The level rows are typed by hand in each season sheet; flag weeks where two sheets disagree."""
    msgs = []
    for d, g in w.dropna(subset=["current_level"]).groupby("survey_date"):
        for col in ("current_level", "last_year_level", "five_year_level"):
            vals = g[col].dropna().unique()
            if len(vals) > 1 and d in current.values():
                msgs.append(f"{d.date()} {col}: " + ", ".join(f"{s} {v:,.0f}" for s, v in zip(g['season'], g[col])))
    return msgs


# ---------------------------------------------------------------------------
# Panel (John's layout, Desk brand)
# ---------------------------------------------------------------------------
def fmt0(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "\u2014"
    return f"{int(np.floor(v + 0.5)):,}"           # half-up, as Excel displays


def panel(season: str, resp: pd.DataFrame, weekly: pd.DataFrame, cur_date: pd.Timestamp,
          last_eos: float | None, out: Path) -> list[Path]:
    ds.use_desk_fonts()
    wk = weekly[weekly["season"] == season].set_index("survey_date").sort_index()
    filled = wk[wk["n"] > 0]
    cur = wk.loc[cur_date]
    prev_dates = filled.index[filled.index < cur_date]
    prev = wk.loc[prev_dates[-1]] if len(prev_dates) else None
    vals = resp[(resp["season"] == season) & (resp["survey_date"] == cur_date)]["estimate_bcf"] \
        .sort_values(ascending=False).to_numpy()

    W, H = ds.COLUMN_IN, 5.0
    fig = plt.figure(figsize=(W, H), facecolor=ds.PAPER)
    fx, fy = (lambda v: v / W), (lambda v: v / H)
    top = H - 0.08
    ds.ribbon(fig, fx(0.06), fy(top - 0.22), fx(W - 0.12), fy(0.22), f"EOS Weekly NG Storage Survey · {season}",
              fontsize=7.5)

    # stats table
    c1, c2, c3, c4 = fx(0.12), fx(1.62), fx(2.18), fx(2.88)
    y0 = top - 0.42
    fig.text(c2, fy(y0), cur_date.strftime("%-d-%b"), color=ds.SURVEY_RED, fontsize=7.5, fontweight="bold", ha="center")
    if prev is not None:
        fig.text(c4, fy(y0), prev.name.strftime("%-d-%b"), color=ds.SURVEY_RED, fontsize=7.5, fontweight="bold", ha="center")
    fig.text(c2, fy(y0 - 0.13), "Current Week", fontsize=6.5, fontweight="bold", ha="center")
    fig.text(c4, fy(y0 - 0.13), "Last Week", fontsize=6.5, fontweight="bold", ha="center")
    rng = lambda r: f"{r['low']:,.0f} to {r['high']:,.0f}"  # noqa: E731
    rows = [("Average", fmt0(cur["average"]), "Bcf", fmt0(prev["average"]) if prev is not None else "\u2014"),
            ("Median", fmt0(cur["median"]), "Bcf", fmt0(prev["median"]) if prev is not None else "\u2014"),
            ("Range", rng(cur), "Bcf", rng(prev) if prev is not None else "\u2014"),
            ("No. of Estimates", f"{int(cur['n'])}", "", f"{int(prev['n'])}" if prev is not None else "\u2014")]
    for i, (lab, a, u, b) in enumerate(rows):
        yy = fy(y0 - 0.30 - 0.135 * i)
        bold = "bold" if lab != "Range" else "normal"
        fig.text(c1, yy, lab, fontsize=6.5, fontweight=bold)
        fig.text(c2, yy, a, fontsize=6.5, fontweight=bold, ha="center")
        fig.text(c3, yy, u, fontsize=6.5, fontweight=bold, ha="center")
        fig.text(c4, yy, b, fontsize=6.5, ha="center")

    # respondent bars, highest to lowest, with the average
    ax = fig.add_axes([fx(0.42), fy(2.62), fx(W - 0.55), fy(1.02)])
    lo = np.floor((vals.min() - 0.15 * (vals.max() - vals.min()) - 100) / 200) * 200
    hi = np.ceil((vals.max() + 100) / 200) * 200
    ax.bar(range(len(vals)), vals - lo, bottom=lo, color=ds.DESK_GREEN, width=0.78, zorder=2)
    ax.axhline(cur["average"], color=ds.SURVEY_RED, ls=(0, (1, 1.5)), lw=1.1, zorder=3)
    ax.text(len(vals) - 0.3, cur["average"], fmt0(cur["average"]), color=ds.INK, fontsize=6,
            va="bottom", ha="left", fontweight="bold")
    for i, v in enumerate(vals):
        ax.text(i, lo + 0.04 * (hi - lo), f"{v:,.0f}", rotation=90, fontsize=4.6, ha="center", va="bottom",
                color=ds.INK, zorder=4)
    ax.set_xlim(-0.6, len(vals) + 2.6)
    ax.set_ylim(lo, hi)
    ax.set_xticks([])
    ax.tick_params(axis="y", labelsize=5.5, length=0, colors=ds.MUTED)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color=ds.GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(ds.INK)
    ax.spines["bottom"].set_linewidth(0.6)

    # storage levels (Lower 48, Bcf)
    y1 = 2.30
    if pd.notna(cur["current_level"]):
        lv = [("Current Level", cur["current_level"], None),
              ("Last Year Level", cur["last_year_level"], cur["current_level"] - cur["last_year_level"]),
              ("5-Year Average Level", cur["five_year_level"], cur["current_level"] - cur["five_year_level"])]
        fig.patches.append(plt.Rectangle((fx(0.06), fy(y1 - 0.47)), fx(W - 0.12), fy(0.62),
                                         transform=fig.transFigure, fc=ds.DESK_GREEN_WASH, ec="none", zorder=-1))
        fig.text(c3, fy(y1 + 0.02), "Bcf", fontsize=6, fontweight="bold", ha="center")
        fig.text(c4, fy(y1 + 0.02), "%", fontsize=6, fontweight="bold", ha="center")
        for i, (lab, v, dlt) in enumerate(lv):
            yy = fy(y1 - 0.15 - 0.14 * i)
            fig.text(c1, yy, lab, fontsize=6.5, fontweight="bold")
            fig.text(c2, yy, fmt0(v), fontsize=6.5, fontweight="bold", ha="center")
            if dlt is not None:
                fig.text(c3, yy, f"{dlt:+,.0f}", fontsize=6.5, fontweight="bold", ha="center")
                fig.text(c4, yy, f"{dlt / v:+.0%}", fontsize=6.5, fontweight="bold", ha="center")

    # weekly survey results: average each week across the season, last-year EOS dashed
    ax2 = fig.add_axes([fx(0.42), fy(0.42), fx(W - 0.55), fy(1.12)])
    allw = wk.index
    av = wk["average"]
    ax2.bar(allw, av.fillna(0), width=2.6, color=ds.DESK_GREEN, zorder=2, label="Average")
    if last_eos:
        ax2.axhline(last_eos, color=ds.CHART_RANGE, ls=(0, (5, 3)), lw=1, zorder=3, label="Last Year EOS")
    ymin = np.floor((min(av.min(), last_eos or av.min()) - 400) / 500) * 500
    ymax = np.ceil((max(av.max(), last_eos or 0) + 300) / 500) * 500
    ax2.set_ylim(ymin, ymax)
    ax2.set_xlim(allw.min() - pd.Timedelta(days=5), allw.max() + pd.Timedelta(days=5))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax2.tick_params(labelsize=5.5, length=0, colors=ds.MUTED)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax2.grid(axis="y", color=ds.GRID, lw=0.5)
    ax2.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.spines["bottom"].set_color(ds.INK)
    ax2.spines["bottom"].set_linewidth(0.6)
    fig.text(fx(0.12), fy(1.62), "Weekly Survey Results", fontsize=6.8, fontweight="bold")
    h, l = ax2.get_legend_handles_labels()
    order = sorted(range(len(l)), key=lambda i: l[i] != "Average")
    ax2.legend([h[i] for i in order], [l[i] for i in order], loc="upper right", bbox_to_anchor=(1.0, 1.22), ncol=2, fontsize=5.3, frameon=False,
               handlelength=1.6, columnspacing=1.0)

    fig.text(fx(0.12), fy(0.10), "Source: Enelyst EOS survey; storage levels: EIA Weekly Natural Gas Storage Report.",
             fontsize=4.6, color=ds.MUTED)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"eos_survey_panel_{season.split()[0].lower()}_{cur_date.strftime('%Y%m%d')}"
    paths = [out / f"{stem}.png", out / f"{stem}.pdf"]
    for p in paths:
        fig.savefig(p, dpi=ds.DPI if p.suffix == ".png" else None, facecolor=ds.PAPER)
    plt.close(fig)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbook", type=Path)
    ap.add_argument("--out", type=Path, default=HOME / "Presentation")
    args = ap.parse_args()
    wbp = args.workbook or max((HOME / "Data").glob("*fall-spring*.xlsx"), key=lambda p: p.stat().st_mtime,
                               default=None)
    if not wbp or not wbp.exists():
        sys.exit("John's survey workbook not found — put it in Data/ (name containing 'fall-spring') or pass --workbook")
    print(f"Reading {wbp.name}")
    resp, weekly, current, last_eos = read_workbook(wbp)
    (HOME / "Data").mkdir(exist_ok=True)
    resp.to_csv(HOME / "Data" / "eos_survey_responses.csv", index=False, date_format="%Y-%m-%d")
    weekly.to_csv(HOME / "Data" / "eos_survey_weekly.csv", index=False, date_format="%Y-%m-%d")
    print(f"  ✓ Data/eos_survey_responses.csv ({len(resp)} estimates, {resp['season'].nunique()} seasons)")
    print(f"  ✓ Data/eos_survey_weekly.csv")
    for msg in check_levels(weekly, current):
        print(f"  ! storage level differs between season sheets — {msg}")
    live = {}
    for s, d in current.items():
        k = s.split()[0]
        if k not in live or int(s.split()[1]) > int(live[k][0].split()[1]):
            live[k] = (s, d)
    for k, (s, d) in sorted(live.items()):
        if (resp["season"].eq(s) & resp["survey_date"].eq(d)).any():
            for p in panel(s, resp, weekly, d, last_eos.get(s), args.out):
                print(f"  ✓ {p.name}")


if __name__ == "__main__":
    main()
