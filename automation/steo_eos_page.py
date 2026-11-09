#!/usr/bin/env python3
"""
steo_eos_page.py — EOS storage vs Henry Hub, with STEO vintages.

Builds one self-contained HTML page (and the JSON behind it) from:
  * Jozef's EOSw.xlsx            weekly end-of-season (EOS) storage estimates
  * Data/eia_prices.csv          daily HH_fut1 / HH_spot from eia_pull.py, weekly-averaged
  * EIA STEO archive workbooks   NGWGPUS − NGWG_AK (Lower 48 working gas, end of period):
                                 October value = fall EOS, March value = spring EOS,
                                 one point per monthly vintage, priced at the release week

Usage:
    python steo_eos_page.py                      # defaults under the project folder
    python steo_eos_page.py --workbook EOSw.xlsx --prices eia_prices.csv --out ./out --cache ./steo_cache

STEO workbooks are cached in --cache; only vintages not yet cached are downloaded
(each month's run fetches just the new release).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eos_desk_chart import (DEFAULT_PRICES, DEFAULT_WB, HOME, exp_trend,  # noqa: E402
                            label_seasons, merge_prices, read_eos_sheet, weekly_prices)

MONS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
ARCHIVE = "https://www.eia.gov/outlooks/steo/archives/{mon}{yy:02d}_base.xlsx"
UA = {"User-Agent": "Mozilla/5.0 (MR Analytics weekly automation)"}


# ---------------------------------------------------------------------------
# STEO vintages
# ---------------------------------------------------------------------------
def steo_release_date(year: int, month: int) -> pd.Timestamp:
    """EIA's rule: first Tuesday after the first Thursday of the month.
    (Occasionally slips to Wednesday after a Monday holiday — same price week.)"""
    d = pd.Timestamp(year, month, 1)
    while d.dayofweek != 3:
        d += pd.Timedelta(days=1)
    return d + pd.Timedelta(days=5)


def fetch_vintage(year: int, month: int, cache: Path) -> Path | None:
    fn = cache / f"{MONS[month - 1]}{year % 100:02d}_base.xlsx"
    if fn.exists():
        return fn
    r = requests.get(ARCHIVE.format(mon=MONS[month - 1], yy=year % 100), headers=UA, timeout=60)
    if r.status_code != 200:
        return None
    fn.write_bytes(r.content)
    return fn


def read_vintage(fn: Path, year: int, month: int) -> list[dict]:
    df = pd.read_excel(fn, "5atab", header=None)
    dates = pd.read_excel(fn, "Dates", header=None)
    last_hist = int(dates.iloc[6, 3])          # YYYYMM of last historical month
    beg_year = int(dates.iloc[2, 3])           # table beginning year (Jan)
    us = df[df[0] == "NGWGPUS"].iloc[0, 2:].to_numpy(float)
    ak = df[df[0] == "NGWG_AK"].iloc[0, 2:].to_numpy(float)
    out = []
    for k, (u, a) in enumerate(zip(us, ak)):
        if np.isnan(u):
            continue
        y, m = beg_year + k // 12, k % 12 + 1
        if m not in (3, 10):
            continue
        out.append({
            "vintage": f"{year}-{month:02d}",
            "release": steo_release_date(year, month).strftime("%Y-%m-%d"),
            "season": ("Spring" if m == 3 else "Fall") + f" {y}",
            "eos_l48": round(float(u - a), 1),
            "eos_us": round(float(u), 1),
            "is_forecast": y * 100 + m > last_hist,
        })
    return out


def steo_vintages(start: tuple[int, int], cache: Path) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today()
    rows, y, m = [], *start
    while (y, m) <= (today.year, today.month):
        fn = fetch_vintage(y, m, cache)
        if fn is None:
            print(f"  STEO {y}-{m:02d}: not published yet / not found")
        else:
            rows += read_vintage(fn, y, m)
        m += 1
        if m == 13:
            y, m = y + 1, 1
    v = pd.DataFrame(rows)
    print(f"  {v.vintage.nunique()} STEO vintages, {start[0]}-{start[1]:02d} → {v.vintage.max()}")
    return v


# ---------------------------------------------------------------------------
# Assemble the data the page needs
# ---------------------------------------------------------------------------
def build_data(workbook: Path, prices: Path, cache: Path) -> dict:
    df, season_cols, latest_label = read_eos_sheet(workbook)
    if prices.exists():
        df = merge_prices(df, weekly_prices(prices))
    else:
        print(f"  {prices} not found — using the workbook's price columns")

    weekly = weekly_prices(prices) if prices.exists() else df[["date", "spot", "futures"]]
    weekly = weekly.set_index("date")

    fall_lab, spring_lab = label_seasons(df, "Fall"), label_seasons(df, "Spring")
    rows = []
    for i, r in df.iterrows():
        if pd.isna(r["fall_all"]) and pd.isna(r["spring_all"]) and pd.isna(r["futures"]):
            continue
        rows.append({
            "date": r["date"].strftime("%Y-%m-%d"),
            "spot": None if pd.isna(r["spot"]) else round(float(r["spot"]), 3),
            "fut": None if pd.isna(r["futures"]) else round(float(r["futures"]), 3),
            "fall": None if pd.isna(r["fall_all"]) else float(r["fall_all"]),
            "spring": None if pd.isna(r["spring_all"]) else float(r["spring_all"]),
            "fall_season": None if pd.isna(fall_lab[i]) else fall_lab[i],
            "spring_season": None if pd.isna(spring_lab[i]) else spring_lab[i],
            "latest": bool(pd.notna(r["latest_fall"]) or pd.notna(r["latest_spring"])),
        })

    # trendlines exactly as the PNG page: all fall history; spring = the three seasons
    # before the current two (Jozef's N46:N199 range)
    fall_year = max(int(s.split()[1]) for s in season_cols if s.startswith("Fall"))
    fm = df["fall_all"].notna() & df["futures"].notna()
    sm = df["spring_all"].notna() & df["futures"].notna() & \
        spring_lab.isin([f"Spring {y}" for y in range(fall_year - 3, fall_year)])
    fa, fb = exp_trend(df.loc[fm, "fall_all"].to_numpy(float), df.loc[fm, "futures"].to_numpy(float))
    sa, sb = exp_trend(df.loc[sm, "spring_all"].to_numpy(float), df.loc[sm, "futures"].to_numpy(float))

    first = df.loc[df["futures"].notna(), "date"].min()
    v = steo_vintages((first.year, first.month), cache)
    rel = pd.to_datetime(v["release"])
    wk_end = rel + pd.to_timedelta((4 - rel.dt.dayofweek) % 7, unit="D")
    v["hh_fut"] = weekly["futures"].reindex(wk_end).round(3).to_numpy()
    v["hh_spot"] = weekly["spot"].reindex(wk_end).round(3).to_numpy()
    v = v.replace({np.nan: None})

    asof = df.loc[df["latest_fall"].notna(), "date"].max()
    return {
        "asof": asof.strftime("%Y-%m-%d"),
        "latest_label": latest_label,
        "fall_year": fall_year,
        "prices_through": df.loc[df["futures"].notna(), "date"].max().strftime("%Y-%m-%d"),
        "trend": {"Fall": [fa, fb], "Spring": [sa, sb]},
        "weekly": rows,
        "steo": v.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def render(data: dict, template: Path) -> str:
    html = template.read_text(encoding="utf-8")
    return html.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbook", type=Path, default=DEFAULT_WB)
    ap.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    ap.add_argument("--cache", type=Path, default=HOME / "Data" / "steo_archive")
    ap.add_argument("--out", type=Path, default=HOME / "Presentation")
    ap.add_argument("--template", type=Path, default=Path(__file__).with_name("steo_eos_template.html"))
    args = ap.parse_args()

    print(f"Reading {args.workbook}")
    data = build_data(args.workbook, args.prices, args.cache)
    args.out.mkdir(parents=True, exist_ok=True)
    tag = data["asof"].replace("-", "")
    (args.out / f"eos_steo_{tag}.json").write_text(json.dumps(data, indent=1))
    (args.out / f"eos_steo_{tag}.html").write_text(render(data, args.template), encoding="utf-8")
    (args.out / "eos_steo_latest.html").write_text(render(data, args.template), encoding="utf-8")
    print(f"  ✓ eos_steo_{tag}.html / .json  (also eos_steo_latest.html)")


if __name__ == "__main__":
    main()
