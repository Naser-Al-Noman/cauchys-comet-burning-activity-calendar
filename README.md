# Cauchy's Comet: The Burning Activity Calendar

## Problem

MODIS active-fire detections at about 1 km resolution have been available since 2000, while VIIRS detections at about 375 m resolution have been available since 2012. These two records are not directly comparable: differences in spatial resolution, overpass timing, and confidence reporting can make a year look like a “record high” for fire activity when part of the signal is a sensor or processing artifact rather than a true change on the ground. We plan to build a calendar-oriented view that harmonizes the two sensors before comparing weeks or seasons across years.

## Questions the app will answer

1. **When does this area normally burn?** We will summarize typical burning activity by week of year for a chosen region.
2. **Is this week unusual compared with past years?** We will compare the current week to a harmonized historical baseline and flag anomalies.
3. **Which periods are critical, and are they shifting?** We will rank high-activity periods and track whether peak timing moves over time.

## Planned approach

We will ingest NASA FIRMS hot-spot archives for MODIS and VIIRS, clean and filter detections, put confidence on a common scale, and aggregate both sensors to a shared spatial and temporal grid. During years when both sensors operated, we will calibrate MODIS to VIIRS using quantile mapping by region and season. On that harmonized record we will build week-of-year baselines, anomaly scores, and summaries of critical burning periods. Details are in [docs/method.md](docs/method.md).

## Planned data sources

We plan to use NASA FIRMS (MODIS and VIIRS), MODIS MCD64A1 burned area for validation, NASA POWER, and NASA GIBS for context layers. Geographic focus is South Asia, with Bangladesh as the demonstration area. See [docs/data_sources.md](docs/data_sources.md).

## Project status

This repository is a **concept-stage proposal** for Team Cauchy's Comet in the [NASA International Space Apps Challenge 2026](https://www.spaceappschallenge.org/) (Bangladesh), challenge **“Harmonization of MODIS and VIIRS Hot Spots.”** It is not a finished product and reports no performance metrics. Implemented pipeline stages include FIRMS download, cleaning, weekly grids, experimental calibration and baselines, critical-period ranking, provenance metadata (Module 2), automated tests, and a static web demo under `web/`. Component-level status and limitations are in [docs/method.md](docs/method.md). Formal validation (held-out years, MCD64A1) and a full-year harmonized archive remain **planned but not implemented**.

## Installation

From the repository root:

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies include `requests`, `pandas`, `numpy`, and `pytest` for automated tests.

## Testing (offline, no NASA API)

Run the full test suite:

```text
python -m pytest
```

Tests use `demo_fixtures/synthetic_firms_bangladesh.csv` only. They do not call the FIRMS API and do not require `FIRMS_MAP_KEY`. Provenance and JSON contract tests are in `tests/test_provenance.py`.

## Offline reproducible pipeline (synthetic data)

Run the end-to-end path without internet access or an API key:

```text
python scripts/run_offline_pipeline.py
```

Default outputs under `cache/offline_repro/`:

| File | Description |
|------|-------------|
| `synthetic_firms_bangladesh_cleaned.csv` | Cleaned detections (duplicates removed) |
| `synthetic_firms_bangladesh_weekly_cells.csv` | Weekly ~5.5 km cell-day aggregates |
| `offline_weekly_totals.csv` | Bangladesh-wide weekly totals |
| `offline_week_of_year_baseline.csv` | Week-of-year baseline percentiles |
| `offline_weekly_scored.csv` | Anomaly scores per week |
| `offline_critical_periods.csv` | Ranked critical ISO weeks |
| `offline_peak_timing.csv` | Peak ISO week per year |
| `offline_calendar.json` | Frontend-shaped JSON (`meta.provenance` + synthetic labels) |
| `offline_provenance.json` | Standalone provenance record (same `provenance_id` as JSON) |

Exported calendar JSON keeps the original **`meta`** fields the web demo reads (`title`, `years`, `status`, etc.) and adds optional **`meta.provenance`** (schema version, input SHA-256, processing configuration, `data_classification`, git commit when available). API keys are never written to exports.

**Synthetic vs real data:** Files under `demo_fixtures/` and JSON from `run_offline_pipeline.py` are **synthetic demonstration inputs/outputs** for pipeline testing. They are not NASA fire observations and must not be cited as real fire statistics. Real FIRMS CSVs from `src.acquire` live in gitignored `cache/` and require a MAP_KEY; label them `real_firms_csv` in provenance when exporting. The committed `web/data/demo_calendar.json` is a separate March-only concept extract from local VIIRS processing (see [web/README.md](web/README.md)); Module 2 does not overwrite it.

Methodology status and known limitations (calibration leakage, in-sample baselines, missing vs zero activity, March-only demo, no MCD64A1 validation) are documented in [docs/method.md](docs/method.md).

## Getting started (real FIRMS download)

1. Request a free [FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key).
2. Copy `.env.example` to `.env` and set `FIRMS_MAP_KEY`.
3. Download a short window for Bangladesh, for example:

```text
python -m src.acquire --source VIIRS_SNPP_NRT --days 3
```

Historical range (5-day chunks; raw chunks under `cache/raw/chunks/`, merged file under `cache/merged/`, manifest under `cache/manifests/`):

```text
python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
```

Optional one-day real-data smoke test (requires `FIRMS_MAP_KEY` in `.env`; key is never printed):

```text
python -m src.acquire --smoke --source VIIRS_SNPP_SP --date 2024-03-04
```

See [src/acquire/README.md](src/acquire/README.md). Downloads are written to `cache/` (gitignored).

Clean and aggregate (weekly ~5.5 km cell-days):

```text
python -m src.compute --input demo_fixtures/synthetic_firms_bangladesh.csv --source VIIRS_SNPP_NRT
```

Calibrate MODIS weekly cells to VIIRS on overlapping cell-weeks:

```text
python -m src.compute.calibrate --modis-weekly cache/<modis>_weekly_cells.csv --viirs-weekly cache/<viirs>_weekly_cells.csv
```

Regional week-of-year baseline + anomaly scores (pass multi-year weekly cell CSVs):

```text
python -m src.compute.baseline --weekly cache/<y1>_weekly_cells.csv cache/<y2>_weekly_cells.csv --prefix viirs_march
```

Critical periods + web demo JSON:

```text
python -m src.compute.critical --baseline cache/viirs_march_week_of_year_baseline.csv --scored cache/viirs_march_weekly_scored.csv --prefix viirs_march --export-json web/data/demo_calendar.json
python -m http.server 8080 --directory web
```

Open http://localhost:8080/ — see [web/README.md](web/README.md).

See [src/compute/README.md](src/compute/README.md). The demo CSV is synthetic for pipeline testing only, not real fire observations. Local `cache/` downloads are gitignored and are not published results. The committed `web/data/demo_calendar.json` is a March-only concept extract from VIIRS processing, labeled as such in the UI.

## Team

All team members are from Bangladesh:

- Naser-Al-Noman
- Zaid Rehman
- Sadman Zaman Khan
- Muhammad Junayed
- Md. Meheraj Hossain
- Israt Jahan Lamia

## Data credit

Data: NASA FIRMS (MODIS, VIIRS)

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
