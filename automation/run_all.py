#!/usr/bin/env python3
"""
run_all.py — the whole weekly chain, one command.

    python automation/run_all.py                       # uses Data/EOSw.xlsx
    python automation/run_all.py --workbook ~/Downloads/EOSw.xlsx
    python automation/run_all.py --fall-title "Full storage, priced as full storage" \
                                 --spring-title "Winter risk is still in the price"
    python automation/run_all.py --skip-prices        # reuse Data/eia_prices.csv as is

Steps: john_survey (if John's workbook is in Data/) → fetch_prices → eos_desk_chart (six-panel PNG) → steo_eos_page (STEO vintages, JSON, HTML)
       → eos_scatter_presentation (fall/spring scatters) → eos_desk_page (InDesign blocks)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("MR_HOME", HERE.parent))


def run(script, *args):
    print(f"\n── {script} {' '.join(args)}")
    r = subprocess.run([sys.executable, str(HERE / script), *args])
    if r.returncode:
        sys.exit(f"{script} failed ({r.returncode})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", default=str(HOME / "Data" / "EOSw.xlsx"))
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--fall-title"); ap.add_argument("--spring-title")
    ap.add_argument("--fall-subtitle"); ap.add_argument("--spring-subtitle")
    a = ap.parse_args()
    out = str(HOME / "Presentation")
    if any((HOME / "Data").glob("*fall-spring*.xlsx")):
        run("john_survey.py", "--out", out)       # survey CSVs + brand-styled survey panels
    else:
        print("\n── John's survey workbook not in Data/ — survey boxes will show the average only")
    if not a.skip_prices:
        run("fetch_prices.py")
    run("eos_desk_chart.py", "--workbook", a.workbook, "--out", out)
    run("steo_eos_page.py", "--workbook", a.workbook, "--out", out)
    extra = []
    for k in ("fall_title", "spring_title", "fall_subtitle", "spring_subtitle"):
        if getattr(a, k):
            extra += ["--" + k.replace("_", "-"), getattr(a, k)]
    run("eos_scatter_presentation.py", "--out", out, *extra)
    run("eos_desk_page.py", "--out", out)
    print(f"\nDone — outputs in {out}")


if __name__ == "__main__":
    main()
