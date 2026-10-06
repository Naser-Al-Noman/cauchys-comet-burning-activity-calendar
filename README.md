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

This repository is a **concept-stage proposal** for Team Cauchy's Comet in the [NASA International Space Apps Challenge 2026](https://www.spaceappschallenge.org/) (Bangladesh), challenge **“Harmonization of MODIS and VIIRS Hot Spots.”** It is not a finished product: there is no deployed app and no reported performance metrics. Early FIRMS download, weekly-grid aggregation, experimental MODIS→VIIRS quantile mapping, and regional week-of-year baseline/anomaly scaffolding live under `src/acquire` and `src/compute`. Critical-period ranking, formal validation, and the calendar UI are still planned.

## Getting started (data download)

1. Request a free [FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key).
2. Copy `.env.example` to `.env` and set `FIRMS_MAP_KEY`.
3. `pip install -r requirements.txt`
4. Download a short window for Bangladesh, for example:

```text
python -m src.acquire --source VIIRS_SNPP_NRT --days 3
```

Historical range (5-day chunks, merged CSV under `cache/`):

```text
python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
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

See [src/compute/README.md](src/compute/README.md). The demo CSV is synthetic for pipeline testing only, not real fire observations. Local `cache/` downloads are gitignored and are not published results.

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
