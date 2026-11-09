# Nat Gas EOS Surveys + — proposed rebuild of The Desk page 4

Prepared for John's review, 9 Nov 2026. Everything below is drawn from real data; nothing is estimated.

## What you'd see

The same six charts in the same positions, delivered each Wednesday as placeable vector PDFs for InDesign:
`eos_charts_2x3_<date>.pdf` (both seasons) or `eos_charts_fall_column_<date>.pdf` + `eos_charts_spring_column_<date>.pdf`.
Sample output for the week ending 30 Oct 2026 is in `Presentation/`.

## What changes vs the current page

| | Current page | Proposed |
|---|---|---|
| Weekly EOS estimates | Jozef's workbook | Same (unchanged) |
| HH Futures line / scatter y-axis | Thomson Reuters weekly figure in the workbook | Mon–Fri average of Yahoo NG=F front-month close. Checked on 252 weeks: matches to the cent except one contract-roll week (1 Nov 2024, 10¢) |
| HH Spot line | Thomson Reuters weekly figure | Mon–Fri average of EIA Henry Hub daily spot (RNGWHHD). Median difference 0.2¢ |
| Scatter trendline | Excel exponential fit | Same fit, same ranges (all fall history; Spring 23–25) |
| **New: STEO triangles** | — | EIA's own end-of-season estimate from each monthly STEO, priced at its release week. Lower 48 basis (US total less Alaska), which matches the storage report and the survey. Forecast vintages only |
| Survey boxes (top of page) | Average, median, range, count, respondent bars | **Not reproduced** — needs the individual survey responses, which aren't in the workbook |

## Decisions we'd like from you

1. **STEO triangles on the scatters: keep, drop, or separate chart?** They add EIA's monthly view but also add ink to a dense chart.
2. **Price source swap: OK?** The Yahoo/EIA series reproduce the Thomson Reuters columns within a few cents and remove a manual paste; the Reuters columns can stay as a fallback.
3. **Survey boxes:** can Jozef export one row per respondent per week? With that we can rebuild the boxes and bars too, and the whole page becomes one file.
4. **Headlines:** the two presentation scatters (`fall_eos_vs_hh_*`, `spring_eos_vs_hh_*`) take an editorial title. For this week we used *"Full storage, priced as full storage"* (fall) and *"Winter risk is still in the price"* (spring); alternatives in the notes below.

## This week's read (30 Oct 2026 data)

**Fall 2026.** Consensus 3,892 Bcf at $2.79 — on the 2022–26 curve ($2.83 implied); every one of the last eight weeks within ±20¢ of it. Fall '25 finished $2.11 above the curve; that premium is gone. EIA's October STEO cut 119 Bcf to 3,817, now 75 Bcf below the survey (≈ $0.48 on the curve). ~3,900 is becoming the normal end-October level: 3,897 (2020), 3,906 (2024), 3,894 (2025).

**Spring 2027.** Consensus 2,030 Bcf at $2.79 — $0.80 above the spring curve ($1.99 implied), and $0.85 above on average for all 16 weeks. EIA's STEO is at 1,858, 172 Bcf below the survey; the price is on the curve at EIA's number, not the survey's. Fall says the market trusts the survey; spring says it doesn't.

Alternative headlines considered: *EIA now sees less gas in storage than the market does* · *A third straight October near 3,900 Bcf*.

## Also available
- Interactive version (scatter with STEO vintages, season timeline, vintage table): `Presentation/eos_steo_latest.html`, also published at https://claude.ai/artifact/AEky5qSTHLo4e71a3HMsqJ
- Method and sources: `README.md`
