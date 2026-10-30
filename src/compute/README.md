# Computation pipeline

Status key: **Implemented and tested** · **Implemented but experimental** · **Planned but not implemented** · **Not yet validated**

| Stage | Module | Status |
|-------|--------|--------|
| Clean + confidence | `clean.py`, `confidence.py`, `python -m src.compute` | **Implemented and tested** |
| Weekly grid | `grid.py` | **Implemented and tested** |
| MODIS→VIIRS calibration | `calibrate.py`, `python -m src.compute.calibrate` | **Implemented but experimental / Not yet validated** |
| Baseline + anomaly | `baseline.py`, `python -m src.compute.baseline` | **Implemented but experimental / Not yet validated** |
| Critical periods + JSON | `critical.py`, `python -m src.compute.critical` | **Implemented but experimental** |
| Provenance metadata | `provenance.py` | **Implemented and tested** |
| Formal validation (MCD64A1, held-out years) | — | **Planned but not implemented** |

Outputs from experimental stages are scaffolding only — not claimed accuracy or climate results.

## Confidence mapping

- MODIS numeric 0–100 → shared 0–1 (`/ 100`)
- VIIRS `l`/`n`/`h` (or low/nominal/high) → 0.3 / 0.6 / 0.9
- Default CLI filter: `--min-confidence 0.0` (keeps all rows that map successfully)

## Aggregation

- Grid cells: `0.05°` (~5.5 km near the equator)
- Each cell-day counts at most once toward weekly totals
- ISO week fields: `iso_year`, `iso_week`, `week_start`

## Usage

```text
pip install -r requirements.txt
python -m src.compute --input demo_fixtures/synthetic_firms_bangladesh.csv --source VIIRS_SNPP_NRT
```

Writes `*_cleaned.csv` and `*_weekly_cells.csv` under `cache/` by default.

### Calibration (MODIS → VIIRS) — experimental

```text
python -m src.compute.calibrate --modis-weekly cache/<modis>_weekly_cells.csv --viirs-weekly cache/<viirs>_weekly_cells.csv
```

Season labels: `dry` (Nov–Feb), `pre_monsoon` (Mar–May), `monsoon` (Jun–Oct).

**Limitation:** Fits on all supplied overlap pairs (calibration leakage); no held-out evaluation in CLI.

### Week-of-year baseline and anomalies — experimental

```text
python -m src.compute.baseline --weekly cache/<year1>_weekly_cells.csv cache/<year2>_weekly_cells.csv ... --prefix viirs_march
```

Anomaly score: `(value - p50) / (0.5 * (p90 - p10))`. `percentile_rank` uses the same years as the baseline (in-sample).

**Limitations:** Missing weeks/cells are not explicit zeros; regional sum only (Bangladesh-wide in default path).

### Critical periods, peak timing, JSON export

```text
python -m src.compute.critical --baseline cache/<prefix>_week_of_year_baseline.csv --scored cache/<prefix>_weekly_scored.csv --prefix viirs_march --export-json web/data/demo_calendar.json
```

Optional provenance fields when exporting JSON:

```text
python -m src.compute.critical ... --export-json out.json --provenance-input cache/source.csv --data-classification real_firms_csv
```

If `--provenance-input` is omitted, input hash and date range in `meta.provenance` are `null`.

### Offline synthetic end-to-end (no API key)

```text
python scripts/run_offline_pipeline.py
```

Writes CSV stages under `cache/offline_repro/`, `offline_provenance.json`, and `offline_calendar.json` with `meta.provenance` and `data_classification: synthetic`.

### Web demo

```text
python -m http.server 8080 --directory web
```

Serves committed `web/data/demo_calendar.json` (March-only concept extract). Frontend does not require `meta.provenance`; older JSON without it remains compatible.

## JSON contract

Top-level keys: `meta`, `baseline`, `weeks`, `critical_periods`, `peak_timing`.

Module 2 adds optional **`meta.provenance`** (structured traceability). See `src/compute/provenance.py` for field definitions.

## Synthetic vs real

- **Synthetic:** `demo_fixtures/synthetic_firms_bangladesh.csv` and offline pipeline JSON — not NASA observations.
- **Real:** FIRMS CSVs from `src.acquire` in `cache/` — require MAP_KEY; classify as `real_firms_csv` in provenance when exporting.

See [docs/method.md](../../docs/method.md) for scientific limitations (calibration leakage, in-sample baselines, missing vs zero activity, March-only demo, no MCD64A1 validation).
