# Computation pipeline

Cleans FIRMS-style detection CSVs, aggregates them to a weekly ~5.5 km grid
(method steps 1–2), and can quantile-map MODIS weekly cells to VIIRS on
overlapping cell-weeks (step 3). Baselines, anomalies, and validation are not
implemented yet. Calibration output is experimental scaffolding, not a claimed
accuracy result.

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

After building weekly tables for both sensors over the same period:

```text
python -m src.compute --input cache/bangladesh_VIIRS_SNPP_SP_2024-03-01_2024-03-31_merged.csv --source VIIRS_SNPP_SP
python -m src.compute --input cache/bangladesh_MODIS_SP_2024-03-01_2024-03-31_merged.csv --source MODIS_SP
python -m src.compute.calibrate --modis-weekly cache/bangladesh_MODIS_SP_2024-03-01_2024-03-31_merged_weekly_cells.csv --viirs-weekly cache/bangladesh_VIIRS_SNPP_SP_2024-03-01_2024-03-31_merged_weekly_cells.csv
```

Season labels used when fitting: `dry` (Nov–Feb), `pre_monsoon` (Mar–May), `monsoon` (Jun–Oct). Season-specific maps are fit only when enough overlap pairs exist; otherwise a global map is used.
