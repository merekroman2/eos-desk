#!/usr/bin/env python3
"""
eos_scatter_presentation.py — presentation scatter charts for The Desk.

Reads the JSON written by steo_eos_page.py (weekly EOS estimates, prices, STEO vintages,
trendlines) and draws, for fall and spring:

    <Season>_eos_vs_hh_<asof>_reference.png   title, subtitle, legend, annotation box
    <Season>_eos_vs_hh_<asof>_clean.png       same frame with tick labels only (Adobe Express layer)

Every number in the annotation is computed from the data on the run; the sentences are
templates that change with the sign and size of the numbers. Titles default to neutral
descriptions — pass --fall-title / --spring-title to use an editorial headline.

Usage:
    python eos_scatter_presentation.py                      # newest Presentation/eos_steo_*.json
    python eos_scatter_presentation.py --json path.json --out dir
    python eos_scatter_presentation.py --fall-title "Full storage, priced as full storage"
"""
from __future__ import annotations

import argparse
import os
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["text.parse_math"] = False

# project root: $MR_HOME if set, else the folder above automation/
HOME = Path(os.environ.get("MR_HOME", Path(__file__).resolve().parent.parent))
PANEL, GRID, INK, MUTED = "#ECEEF1", "white", "#1f2328", "#444"
CURVE, LATEST = "#C9611C", "#D62728"
PAL = {  # oldest -> newest of the five seasons shown
    "Fall":   ["#8C8C8C", "#3C86C9", "#4FAE5B", "#7030A0", "#ED7D31"],
    "Spring": ["#8C8C8C", "#4FAE5B", "#3C86C9", "#F4A26B", "#C00000"],
}
XLIM = {"Fall": (3200, 4200), "Spring": (1400, 2400)}
YLIM = {"Fall": (0, 14), "Spring": (0, 7)}
STEO_FACE = {"Fall": "#ED7D31", "Spring": "#C00000"}


def money(v: float) -> str:
    return f"${v:.2f}"


def season_stats(kind: str, d: dict) -> dict:
    """Numbers for the annotation; all derived from the JSON."""
    key = kind.lower()
    skey = key + "_season"
    w = pd.DataFrame(d["weekly"])
    s = pd.DataFrame(d["steo"])
    a, b = d["trend"][kind]
    f = lambda x: a * np.exp(b * x)  # noqa: E731

    w = w[w[key].notna() & w["fut"].notna()].copy()
    w["resid"] = w["fut"] - f(w[key])
    seasons = sorted(w[skey].unique(), key=lambda x: int(x.split()[1]))[-5:]
    cur, prev = seasons[-1], seasons[-2]
    last = w[w["latest"] & (w[skey] == cur)].iloc[-1]
    prev_last = w[w[skey] == prev].iloc[-1]
    cur_rows = w[w[skey] == cur]

    st = s[(s["season"] == cur) & s["is_forecast"] & s["hh_fut"].notna()].sort_values("vintage")
    steo = None
    if len(st):
        r = st.iloc[-1]
        steo = dict(vintage=r["vintage"], eos=r["eos_l48"], price=r["hh_fut"], implied=f(r["eos_l48"]),
                    change=(r["eos_l48"] - st.iloc[-2]["eos_l48"]) if len(st) > 1 else None,
                    gap_bcf=r["eos_l48"] - last[key], gap_usd=f(r["eos_l48"]) - f(last[key]))

    return dict(kind=kind, seasons=seasons, cur=cur, prev=prev, trend=(a, b),
                date=pd.Timestamp(last["date"]), eos=last[key], price=last["fut"],
                implied=f(last[key]), resid=last["resid"], resid_season=cur_rows["resid"].mean(),
                prev_resid_end=prev_last["resid"], slope100=np.exp(b * 100) - 1,
                n_weeks=len(cur_rows), steo=steo, st=st, w=w, last=last)


def annotation_text(x: dict) -> str:
    short = x["cur"].replace(" 20", " ’")
    pshort = x["prev"].replace(" 20", " ’")
    date = x["date"].strftime("%b %-d")
    r = x["resid"]
    if abs(r) < 0.15:
        where = f"on the curve ({money(x['implied'])} implied)"
    else:
        where = f"{money(abs(r))} {'above' if r > 0 else 'below'} the curve ({money(x['implied'])} implied)"
    lines = [f"{date}: consensus {x['eos']:,.0f} Bcf at {money(x['price'])} — {where}."]

    rs = x["resid_season"]
    if abs(rs) >= 0.3 and x["n_weeks"] >= 6:
        lines.append(f"{short} has averaged {money(abs(rs))} {'above' if rs > 0 else 'below'} the curve over {x['n_weeks']} weeks.")
    pr = x["prev_resid_end"]
    if abs(pr) >= 0.3:
        lines.append(f"{pshort} finished {money(abs(pr))} {'above' if pr > 0 else 'below'} the curve"
                     + ("; that premium is gone." if pr > 0 and abs(r) < 0.15 else "."))

    st = x["steo"]
    if st:
        vint = pd.Timestamp(st["vintage"] + "-01").strftime("%b")
        chg = f"cut {abs(st['change']):,.0f} Bcf to" if st["change"] is not None and st["change"] < 0 else \
              (f"raised {st['change']:,.0f} Bcf to" if st["change"] else "has")
        side = "below" if st["gap_bcf"] < 0 else "above"
        lines.append(f"EIA’s {vint} STEO {chg} {st['eos']:,.0f}, {abs(st['gap_bcf']):,.0f} Bcf {side} the survey "
                     f"(≈ {money(abs(st['gap_usd']))} on the curve).")
    lines.append(f"Curve slope ≈ {abs(x['slope100'])*100:.0f}% in price per 100 Bcf.")
    return "\n".join(lines[:4])


def draw(x: dict, out: Path, tag: str, title: str | None, subtitle: str | None, clean: bool) -> Path:
    kind, key = x["kind"], x["kind"].lower()
    skey = key + "_season"
    a, b = x["trend"]
    w, st, last = x["w"], x["st"], x["last"]
    x0, x1 = XLIM[kind]

    fig, ax = plt.subplots(figsize=(14, 8), dpi=100)
    ax.set_facecolor(PANEL)
    ax.set_axisbelow(True)
    ax.grid(True, color=GRID, lw=1.2)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    xs = np.linspace(x0, x1, 200)
    ax.plot(xs, a * np.exp(b * xs), ls=(0, (1.5, 2.5)), color=CURVE, lw=2, zorder=2)
    for i, sname in enumerate(x["seasons"]):
        g = w[w[skey] == sname]
        cur = sname == x["cur"]
        ax.scatter(g[key], g["fut"], s=42 if cur else 32, color=PAL[kind][i], alpha=1 if cur else 0.85,
                   edgecolors="white", linewidths=0.5, label=sname.replace(" 20", " ’"), zorder=5 if cur else 3)
    cshort = x["cur"].replace(" 20", " ’")
    if len(st):
        ax.scatter(st["eos_l48"], st["hh_fut"], marker="^", s=130, facecolor=STEO_FACE[kind], edgecolor=INK,
                   lw=1.1, label=f"EIA STEO, {cshort} vintages", zorder=6)
    ax.scatter([last[key]], [last["fut"]], marker="D", s=120, color=LATEST, edgecolor="white", lw=1.2,
               label=f"Week ending {x['date'].strftime('%b %-d')}", zorder=7)
    ax.set_xlim(x0, x1)
    ax.set_ylim(*YLIM[kind])
    ax.tick_params(labelsize=16, length=4, colors=MUTED)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    suffix = "clean" if clean else "reference"
    fn = out / f"{key}_eos_vs_hh_{tag}_{suffix}.png"
    if not clean:
        ax.set_xlabel(f"{kind} end-of-season storage estimate, Lower 48 (Bcf)", fontsize=14, color=MUTED)
        ax.set_ylabel("Prompt-month Henry Hub ($/MMBtu, week average)", fontsize=14, color=MUTED)
        title = title or f"{kind} end-of-season storage vs Henry Hub"
        yrs = f"{x['seasons'][0].split()[1]}–{x['seasons'][-1].split()[1]}"
        subtitle = subtitle or (f"Weekly end-of-season storage estimates vs prompt-month Henry Hub, {kind} {yrs},\n"
                                f"with EIA’s monthly STEO estimates for {x['cur']}. Dotted: exponential fit.")
        ax.text(0.01, 0.97, title, transform=ax.transAxes, fontsize=20, fontweight="bold", va="top", color=INK,
                bbox=dict(fc=PANEL, ec="none", pad=2))
        ax.text(0.01, 0.91, subtitle, transform=ax.transAxes, fontsize=12.5, va="top", color=MUTED,
                bbox=dict(fc=PANEL, ec="none", pad=2))
        # annotation box in the upper-right quadrant, arrow to the latest point
        bx = x0 + 0.38 * (x1 - x0)
        by = YLIM[kind][0] + 0.74 * (YLIM[kind][1] - YLIM[kind][0])
        ax.annotate(annotation_text(x), xy=(last[key], last["fut"]), xytext=(bx, by), fontsize=12.5, color=INK,
                    va="top", bbox=dict(boxstyle="round,pad=0.6", fc="white", ec=LATEST, lw=1.2),
                    arrowprops=dict(arrowstyle="-", color=LATEST, lw=1, connectionstyle="arc3,rad=0.25"), zorder=8)
        ax.legend(loc="lower left", fontsize=12, frameon=True, facecolor="white", edgecolor="#DADADA", markerscale=1.1)
        ax.text(0.99, -0.11, "Sources: weekly EOS survey (Jozef); Yahoo NG=F front-month, Mon–Fri weekly average; "
                "EIA STEO table 5a, NGWGPUS less Alaska, priced at release week. MR Analytics for Enelyst.",
                transform=ax.transAxes, fontsize=9.5, color="#777", ha="right")
    plt.tight_layout()
    fig.savefig(fn, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fn


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path, help="eos_steo_<asof>.json (default: newest in --out)")
    ap.add_argument("--out", type=Path, default=HOME / "Presentation")
    ap.add_argument("--fall-title"); ap.add_argument("--fall-subtitle")
    ap.add_argument("--spring-title"); ap.add_argument("--spring-subtitle")
    args = ap.parse_args()

    js = args.json or max(args.out.glob("eos_steo_*.json"), default=None)
    if not js or not js.exists():
        sys.exit("No eos_steo_<asof>.json found — run steo_eos_page.py first")
    d = json.loads(js.read_text())
    tag = d["asof"].replace("-", "")
    print(f"Reading {js.name}")
    for kind, t, sub in (("Fall", args.fall_title, args.fall_subtitle), ("Spring", args.spring_title, args.spring_subtitle)):
        x = season_stats(kind, d)
        print(f"\n{kind}: {annotation_text(x).replace(chr(10), ' | ')}")
        for clean in (False, True):
            print(f"  ✓ {draw(x, args.out, tag, t, sub, clean).name}")


if __name__ == "__main__":
    main()
