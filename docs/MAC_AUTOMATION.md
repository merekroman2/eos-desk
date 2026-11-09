# EOS Desk chart — setup on the Mac

1. Copy `eos_desk_chart.py` into `~/Claude Projects/MR Analytics - Energy Blog/automation/`
2. Drop Jozef's workbook at `Data/EOSw.xlsx` (overwrite each week when he sends a new one).
3. Test:  `~/.venvs/enelyst-energy/bin/python automation/eos_desk_chart.py`
   Outputs land in `Presentation/`: `eos_desk_<asof>_reference.png`, `_clean.png`, `_data.csv`.
4. Add to `automation/run_weekly.sh` after the forward-curve and CFTC steps:

    # EOS vs Henry Hub page (Jozef's EOSw.xlsx must be in Data/)
    if [ -f "$HOME_DIR/Data/EOSw.xlsx" ]; then
        "$PY" "$HOME_DIR/automation/eia_pull.py" --save >> "$LOG" 2>&1
        "$PY" "$HOME_DIR/automation/eos_desk_chart.py" >> "$LOG" 2>&1 \
          && cp "$HOME_DIR"/Presentation/eos_desk_*_reference.png \
                "$HOME_DIR"/Presentation/eos_desk_*_clean.png \
                "$HOME_DIR/Weekly_Enelyst/$RUN_DATE/"
    else
        echo "EOSw.xlsx not in Data/ — skipped EOS page" >> "$LOG"
    fi

   (Adjust `$PY`, `$HOME_DIR`, `$LOG`, `$RUN_DATE` to whatever names run_weekly.sh already uses.)

## What the script reads
- Sheet `EOS`: col A week, B HH spot, C HH futures, F..M one column per season
  (`EOS Fall 2026`, `EOS Spring 2027`, …), N/O all-spring / all-fall, P/Q the latest-week marker.
- Y-axis ranges are taken from Jozef's own Excel charts (bar + line combos) so the panels match his;
  if a chart can't be found it falls back to auto-scaling.
- Fall 2022 and Spring 2023 have no dedicated column, so they are labelled by date from the N/O columns.
- Trendlines: Excel "Exponential" (OLS on ln(price)) on the same ranges his charts use —
  all fall history, and Spring 23–25 for the spring panel.

## Prices
By default prices come from our own feed, not the Thomson Reuters columns: `Data/eia_prices.csv`
(written by `eia_pull.py --save`) is averaged Mon–Fri into week-ending-Friday values, which is
exactly how Jozef builds his HH Futures column (weekly average of CME prompt settlements; his
HH Spot is the EIA weekly-average Henry Hub spot). Checked on 252 overlapping weeks: futures match
to the cent except one contract-roll week (2024-11-01, 0.10), spot median difference 0.002.
Weeks missing from our file fall back to the workbook's columns; `--workbook-prices` uses his columns only.
The log prints the overlap comparison every run, so a bad Yahoo pull shows up immediately.

Because eia_pull.py runs daily, the price lines run one week past Jozef's last EOS estimate
(as in John's page). Make sure `eia_pull.py --save` runs before this script in run_weekly.sh.

## Not automated
The EOS estimates are Jozef's input; the script never fills or extends them. If his file is a
week behind, the bars and the red marker will be too (the as-of date is in the filename).

## Interactive page with STEO vintages — `steo_eos_page.py`
Same folder, same venv. Needs `steo_eos_template.html` next to it and imports from `eos_desk_chart.py`.

    "$PY" "$HOME_DIR/automation/steo_eos_page.py" >> "$LOG" 2>&1

Reads EOSw.xlsx + eia_prices.csv as above, plus the STEO archive workbooks
(`https://www.eia.gov/outlooks/steo/archives/<mon><yy>_base.xlsx`, cached in `Data/steo_archive/`;
only the newest release is downloaded each month). From each vintage it takes table 5a
NGWGPUS − NGWG_AK (Lower 48 end-of-period working gas): the October value for the fall season, the
March value for spring — verified: Jul 2026 vintage gives 3,932.7 Bcf, Jozef's "EOS EIA STEO" cell is 3,933.
Release dates follow EIA's rule (first Tuesday after the first Thursday); the price is the Mon–Fri
average of that release week. Only forecast vintages are plotted (after a season ends, STEO carries
the actual, which isn't an estimate).

Outputs: `Presentation/eos_steo_<asof>.html` + `.json`, and `eos_steo_latest.html`.
To refresh the published Claude artifact, upload the new `eos_steo_latest.html` to the same artifact
(or ask Claude to republish it with the new file).

## Presentation scatters for The Desk — `eos_scatter_presentation.py`
Runs after `steo_eos_page.py` (reads its JSON). Writes, for fall and spring,
`<season>_eos_vs_hh_<asof>_reference.png` and `_clean.png` (grey panel, white grid, tick labels on both;
the clean one has no title/legend/annotation for Adobe Express). The annotation box is computed each
week — where the latest point sits vs the curve, the season average, the prior season's finish, EIA's
latest STEO vs the survey in Bcf and $ — so it never needs editing, but the title is editorial:
default is neutral ("Fall end-of-season storage vs Henry Hub"); pass `--fall-title` / `--spring-title`
(and `--*-subtitle`) when you want a headline.

    "$PY" "$HOME_DIR/automation/eos_scatter_presentation.py" >> "$LOG" 2>&1 \
      && cp "$HOME_DIR"/Presentation/*_eos_vs_hh_*.png "$HOME_DIR/Weekly_Enelyst/$RUN_DATE/"

## The Desk chart block — `eos_desk_page.py`
John assembles the page in InDesign, so the deliverables are the chart block, not the page:
`eos_charts_2x3_<asof>.pdf` (both banners + six charts, 7.5 x 7.6 in) and the two columns
`eos_charts_fall_column_<asof>.pdf` / `eos_charts_spring_column_<asof>.pdf` (3.65 x 7.6 in each),
all vector PDF with a PNG twin. The full-page mock-up below is also written but is just a reference.

## The Desk page (portrait, reference only)
Runs after `steo_eos_page.py`; writes `Presentation/eos_desk_page_<asof>.png` and `.pdf` (8.5 x 11) in
John's page layout: title band, two survey boxes, FALL/SPRING banners, six charts. The survey boxes show
the weekly average (current vs last week) from the workbook; median, range, number of estimates and
the per-respondent bar strips need the survey file, which the workbook does not contain — wire that in
once Jozef shares it. The scatters carry the EIA STEO triangles.

    "$PY" "$HOME_DIR/automation/eos_desk_page.py" >> "$LOG" 2>&1 \
      && cp "$HOME_DIR"/Presentation/eos_charts_*_"$(date +%Y%m%d)"*.pdf "$HOME_DIR/Weekly_Enelyst/$RUN_DATE/"
