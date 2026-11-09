# EOS storage vs Henry Hub — weekly charts for The Desk

Builds the "Nat Gas EOS Surveys +" chart block (and a few extras) from the weekly end-of-season
storage survey, public Henry Hub prices and EIA's monthly STEO. Everything is drawn from real data;
nothing is estimated or filled in.

## Quick start

```bash
git clone <this repo> eos-desk && cd eos-desk
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp /path/to/EOSw.xlsx Data/EOSw.xlsx                     # the weekly survey workbook (not in the repo)
python automation/run_all.py
```

Outputs land in `Presentation/`. First run downloads ~58 STEO archive workbooks (about 1 MB each)
into `Data/steo_archive/`; later runs only fetch the newest release.

## What you get each week

| File | What it is |
|---|---|
| `eos_charts_2x3_<asof>.pdf` / `.png` | The Desk chart block: FALL / SPRING banners + six charts, 7.5 × 7.6 in, vector |
| `eos_charts_fall_column_<asof>.pdf`, `eos_charts_spring_column_<asof>.pdf` | Same, one season per file (3.65 × 7.6 in) for separate placement in InDesign |
| `fall_eos_vs_hh_<asof>_reference.png`, `spring_…_reference.png` | Presentation scatters with title, legend and a computed annotation box |
| `fall_eos_vs_hh_<asof>_clean.png`, `spring_…_clean.png` | Same frame, ticks only, for Adobe Express |
| `eos_desk_<asof>_reference.png` / `_clean.png` | The original six-panel landscape page |
| `eos_steo_<asof>.html` (+ `eos_steo_latest.html`, `.json`) | Interactive page: scatter with STEO vintages, season timeline, vintage table |
| `eos_desk_page_<asof>.pdf` | Full-page mock-up of page 4, reference only |

Titles on the presentation scatters default to neutral text; pass `--fall-title` / `--spring-title`
to `run_all.py` for a headline.

## Data

- **Weekly EOS estimates** — `Data/EOSw.xlsx`, sheet `EOS`: column A week, F..M one column per season
  (`EOS Fall 2026`, `EOS Spring 2027`, …), N/O all spring / all fall, P/Q the latest-week marker.
  Y-axis ranges for the bar charts are read from the workbook's own charts, so edits there carry over.
- **Prices** — `Data/eia_prices.csv`, written by `automation/fetch_prices.py`: Yahoo NG=F front-month
  close and EIA Henry Hub daily spot (RNGWHHD). The scripts average Mon–Fri into week-ending-Friday
  values, which matches the workbook's HH Futures column (weekly average of CME prompt settlements) to
  the cent and its HH Spot column within a few cents. The workbook's own Thomson Reuters price columns
  are used only for weeks the CSV lacks, or with `--workbook-prices`.
- **STEO** — EIA archive workbooks `https://www.eia.gov/outlooks/steo/archives/<mon><yy>_base.xlsx`,
  table 5a, series `NGWGPUS − NGWG_AK` = Lower 48 end-of-period working gas. October value = fall
  EOS, March value = spring EOS. Lower 48 is the right basis: the Jul 2026 vintage gives 3,932.7 Bcf
  and the workbook's "EOS EIA STEO" cell is 3,933. Release dates follow EIA's rule (first Tuesday
  after the first Thursday); each vintage is priced at the Mon–Fri average of its release week. Only
  forecast vintages are plotted — after a season ends STEO carries the actual, which is not an estimate.
- **Trendlines** — Excel-style exponential fit (OLS on ln price): all fall history for fall; the
  three spring seasons before the current two for spring (the ranges the workbook's charts use).

## Scripts (`automation/`)

| Script | Role |
|---|---|
| `fetch_prices.py` | key-free price feed → `Data/eia_prices.csv` |
| `eos_desk_chart.py` | reads the workbook, merges prices, six-panel landscape page; shared functions |
| `steo_eos_page.py` | STEO vintages, data JSON, interactive HTML (template: `steo_eos_template.html`) |
| `eos_scatter_presentation.py` | fall/spring presentation scatters with computed annotation |
| `eos_desk_page.py` | The Desk chart block, columns, and full-page mock-up |
| `run_all.py` | runs the chain |

Set `MR_HOME=/some/folder` to use a different project root than the repo folder.

## Not in the workbook

The survey boxes at the top of The Desk's page (median, range, number of estimates and the
per-respondent bars) need the individual survey responses, which the workbook does not contain, so the
full-page mock-up leaves those rows blank. Add a sheet with one row per respondent per week and they
can be wired in.
