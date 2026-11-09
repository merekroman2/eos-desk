#!/usr/bin/env python3
"""
fetch_prices.py — build Data/eia_prices.csv without an EIA API key.

  HH_fut1  Yahoo Finance NG=F front-month close (daily)
  HH_spot  EIA Henry Hub daily spot (RNGWHHD), scraped from the public dnav page

This is the key-free stand-in for eia_pull.py --save; the downstream scripts read the same
columns. Existing rows are kept and new days appended, so history is never lost if a source
is down for a day.
"""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

import pandas as pd
import requests

HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))
OUT = HOME / "Data" / "eia_prices.csv"
UA = {"User-Agent": "Mozilla/5.0 (MR Analytics weekly automation)"}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def yahoo_front_month(start: str) -> pd.Series:
    import yfinance as yf
    for attempt in range(3):
        df = yf.download("NG=F", start=start, progress=False, auto_adjust=False)
        if len(df):
            s = df["Close"].squeeze()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            return s.rename("HH_fut1")
    sys.exit("Yahoo returned no data for NG=F after 3 tries")


def eia_spot() -> pd.Series:
    r = requests.get("https://www.eia.gov/dnav/ng/hist/rngwhhdD.htm", headers=UA, timeout=60)
    r.raise_for_status()
    tabs = pd.read_html(io.StringIO(r.text))
    t = max([x for x in tabs if x.shape[1] == 6 and x.shape[0] > 50], key=len)
    t.columns = ["wk", "M", "T", "W", "Th", "F"]
    rows = {}
    for _, row in t.iterrows():
        m = re.match(r"(\d{4})\s+(\w{3})-\s*(\d+)\s+to\s+(\w{3})-\s*(\d+)", str(row["wk"]))
        if not m:
            continue
        yr, m1, _, m2, d2 = m.groups()
        yr = int(yr) + (1 if MONTHS[m2] < MONTHS[m1] else 0)   # week that wraps the year
        end = pd.Timestamp(yr, MONTHS[m2], int(d2))
        for i, c in enumerate(["M", "T", "W", "Th", "F"]):
            v = pd.to_numeric(row[c], errors="coerce")
            if pd.notna(v):
                rows[end - pd.Timedelta(days=4 - i)] = float(v)
    return pd.Series(rows).sort_index().rename("HH_spot")


def main():
    start = "2021-12-01"
    old = None
    if OUT.exists():
        old = pd.read_csv(OUT, parse_dates=["date"]).set_index("date")
        start = (old.index.max() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    new = pd.concat([yahoo_front_month(start), eia_spot()], axis=1, sort=True)
    new = new[new.index >= pd.Timestamp(start)]
    df = pd.concat([old[~old.index.isin(new.index)], new]).sort_index() if old is not None else new
    df.index.name = "date"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT)
    print(f"  ✓ {OUT.relative_to(HOME)}  {df.index.min().date()} → {df.index.max().date()}  "
          f"(fut through {df['HH_fut1'].dropna().index.max().date()}, spot through {df['HH_spot'].dropna().index.max().date()})")


if __name__ == "__main__":
    main()
