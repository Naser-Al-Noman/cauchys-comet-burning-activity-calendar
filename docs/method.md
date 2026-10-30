# Method and implementation status

This document describes **what the repository implements today**, how each stage works, and known scientific limitations. Status labels:

| Label | Meaning |
|-------|---------|
| **Implemented and tested** | Code exists; covered by automated tests (Module 1+) |
| **Implemented but experimental** | Code exists; not scientifically validated |
| **Planned but not implemented** | Described in docs or README only |
| **Not yet validated** | Implemented code with no independent accuracy checks |

## 1. Clean detections and harmonize confidence — **Implemented and tested**

**Code:** `src/compute/clean.py`, `src/compute/confidence.py`, CLI `python -m src.compute`

- Loads FIRMS-shaped CSVs; requires `latitude`, `longitude`, `acq_date`, `confidence`.
- MODIS numeric 0–100 → shared 0–1 scale; VIIRS `l`/`n`/`h` (and word forms) → 0.3 / 0.6 / 0.9.
- Drops invalid coordinates, rows missing confidence after mapping, and exact duplicates on `(lat, lon, acq_date[, acq_time])`.
- Default `--min-confidence` is **0.0** (no high-confidence filter unless the user sets one).

**Limitations (documented, not fixed in Module 2):**

- Confidence thresholds are not tuned against challenge requirements or independent validation.
- MODIS and VIIRS confidence are harmonized ordinally, not proven equivalent for fire detection.

## 2. Weekly spatial aggregation — **Implemented and tested**

**Code:** `src/compute/grid.py`

- Fixed grid: **0.05°** cells (~5.5 km near the equator; smaller at Bangladesh latitudes).
- Each **cell-day** counts at most once per week aggregation.
- Temporal bucket: **ISO week** (`iso_year`, `iso_week`, `week_start` = Monday of that week).
- Aggregation uses **`acq_date` only**; `acq_time` is not used for weekly grouping.

**Limitations:**

- **Missing observations vs zero activity:** Weeks/cells with no detections are absent from the grid; they are not explicit zeros. Quiet periods can be indistinguishable from missing data (clouds, gaps, no overpass).
- **Spatial resolution:** MODIS (~1 km) and VIIRS (~375 m) native resolutions differ; the shared 0.05° grid does not equalize detection sensitivity.

## 3. MODIS → VIIRS calibration — **Implemented but experimental / Not yet validated**

**Code:** `src/compute/calibrate.py`, CLI `python -m src.compute.calibrate`

- Empirical **quantile mapping** on overlapping MODIS/VIIRS **cell-weeks**, with optional season splits (Bangladesh-oriented dry / pre_monsoon / monsoon).
- Writes overlap table and `modis_weekly_cells_calibrated.csv`.

**Limitations:**

- **Calibration leakage:** Models are fit on all overlapping pairs in the supplied files; there is no held-out year split in the current CLI.
- Not used in the default offline synthetic pipeline (`calibration.status: not_applied`).
- No reported accuracy metrics vs VIIRS or burned area.

## 4. Week-of-year baseline and anomaly score — **Implemented but experimental / Not yet validated**

**Code:** `src/compute/baseline.py`, CLI `python -m src.compute.baseline`

- Sums weekly cells to a **Bangladesh-wide** regional series (not per-cell baselines in the demo).
- Baseline: p10 / p50 / p90 by **ISO week** across years in the input files.
- Anomaly score: `(value - p50) / (0.5 * (p90 - p10))` with simple edge handling when p90 = p10.
- `percentile_rank` is computed **in-sample** against the same years used to build the baseline.

**Limitations:**

- **Baseline in-sample scoring:** The same weeks used to define percentiles are also scored against them; this is not leave-one-year-out or held-out validation.
- Weeks with fewer than `--min-years` years are flagged (`enough_years=False`) but still appear in outputs.

## 5. Critical periods and peak timing — **Implemented but experimental**

**Code:** `src/compute/critical.py`, CLI `python -m src.compute.critical`

- Ranks ISO weeks by baseline **p50** (prefers weeks with `enough_years` when available).
- Peak timing: busiest ISO week per year; optional descriptive slope of peak ISO week vs year (≥2 years).

**Limitations:**

- Descriptive only; not an operational fire warning.
- Peak slope is easily misleading on short or seasonal extracts (e.g. March-only).

## 6. Data acquisition — **Implemented and tested (download only)**

**Code:** `src/acquire/` — FIRMS Area API client, Bangladesh bbox, batch merge to `cache/`

- Requires `FIRMS_MAP_KEY` in environment or `.env` (never embedded in JSON exports).
- Does not run in offline synthetic tests.

## 7. Provenance and JSON export — **Implemented and tested (Module 2)**

**Code:** `src/compute/provenance.py`, `export_demo_calendar_json` in `critical.py`

- Calendar JSON includes `meta.provenance` with schema version, input SHA-256, processing config, classification (`synthetic` vs `real_firms_csv`), git commit when available, and timestamps.
- Offline run also writes `{prefix}_provenance.json` beside CSV outputs.

## 8. Static web demo — **Implemented (demo) / Not yet validated**

**Code:** `web/` — reads committed `web/data/demo_calendar.json`

- **March-only** ISO weeks in the committed demo extract (not a full-year calendar).
- UI labels the product as concept-stage; hot spots ≠ burned area.
- Frontend unchanged in Module 2; older JSON without `meta.provenance` remains valid.

## 9. Validation — **Planned but not implemented**

Not implemented in this repository:

- Held-out years for calibration or baselines.
- Comparison to **MODIS MCD64A1** burned area.
- NASA POWER / GIBS ingestion.
- Published accuracy or bias metrics.

**Known gaps to state in any public claim:**

| Topic | Status |
|-------|--------|
| Calibration leakage | Present in current fit-on-all-overlap design |
| In-sample baseline/anomaly | Present |
| Missing vs zero fire activity | Not modeled |
| Sensor resolution differences | Partially mitigated only if calibration is applied |
| Confidence filtering | Optional; default keeps all mapped confidence levels |
| March-only frontend demo | Committed `web/data/demo_calendar.json` |
| Independent burned-area validation | **Not performed** |

No validation results or performance numbers should be claimed until those modules are implemented and executed.
