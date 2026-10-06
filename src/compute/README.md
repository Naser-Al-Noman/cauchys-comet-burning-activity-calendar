# Computation pipeline

Cleans FIRMS-style detection CSVs and aggregates them to a weekly ~5.5 km grid (method steps 1–2). Calibration, baselines, and validation are not implemented yet.

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

Use a real download from `src.acquire` the same way once `FIRMS_MAP_KEY` is set.
