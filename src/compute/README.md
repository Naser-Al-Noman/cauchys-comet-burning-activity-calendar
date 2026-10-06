# Computation pipeline

Cleans FIRMS-style detection CSVs, aggregates them to a weekly ~5.5 km grid
(method steps 1–2), quantile-maps MODIS to VIIRS on overlapping cell-weeks
(step 3), and builds regional week-of-year baselines with anomaly scores
(step 4). Critical-period ranking and formal validation are not implemented
yet. Outputs are experimental scaffolding, not claimed accuracy or climate
results.

## Confidence mapping

- MODIS numeric 0–100 → shared 0–1 (`/ 100`)
- VIIRS `l`/`n`/`h` (or low/nominal/high) → 0.3 / 0.6 / 0.9

## Aggregation

- Grid cells are `0.05°` ≈ 5.5 km near the equator
- Each cell-day counts at most once
- Weekly totals use ISO week (`iso_year`, `iso_week`, `week_start`)

## Usage

```text
pip install -r requirements.txt
python -m src.compute --input demo_fixtures/synthetic_firms_bangladesh.csv --source VIIRS_SNPP_NRT
```

Writes `*_cleaned.csv` and `*_weekly_cells.csv` under `cache/` by default.

### Calibration (MODIS → VIIRS)

```text
python -m src.compute.calibrate --modis-weekly cache/<modis>_weekly_cells.csv --viirs-weekly cache/<viirs>_weekly_cells.csv
```

Season labels: `dry` (Nov–Feb), `pre_monsoon` (Mar–May), `monsoon` (Jun–Oct).

### Week-of-year baseline and anomalies

Sum weekly cells to a Bangladesh-wide series, then build p10/p50/p90 by ISO week
across years and score each week:

```text
python -m src.compute.baseline --weekly cache/<year1>_weekly_cells.csv cache/<year2>_weekly_cells.csv ... --prefix viirs_march
```

Anomaly score is `(value - p50) / (0.5 * (p90 - p10))`. `percentile_rank` is the
share of same-ISO-week samples that are ≤ the week’s value. Weeks with fewer
than `--min-years` years are flagged via `enough_years=False`.

### Critical periods and peak timing

```text
python -m src.compute.critical --baseline cache/viirs_march_week_of_year_baseline.csv --scored cache/viirs_march_weekly_scored.csv --prefix viirs_march --export-json web/data/demo_calendar.json
```

### Web demo

```text
python -m http.server 8080 --directory web
```

Then open http://localhost:8080/
