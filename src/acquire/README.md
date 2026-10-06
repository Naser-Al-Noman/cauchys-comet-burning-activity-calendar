# Data acquisition

Download NASA FIRMS active-fire CSV for the Bangladesh demonstration area.

## Setup

1. Create a free [FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key).
2. Copy `.env.example` to `.env` and set `FIRMS_MAP_KEY`.
3. From the repo root:

```text
pip install -r requirements.txt
```

## Single window (1–5 days)

```text
python -m src.acquire --source VIIRS_SNPP_NRT --days 3
python -m src.acquire --source MODIS_SP --days 5 --date 2024-01-01 --out cache/modis_bd.csv
```

## Historical batch (date range)

The Area API allows only 1–5 days per request. Batch mode walks the range in chunks, writes each chunk under `cache/chunks/`, and builds a merged CSV.

```text
python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
python -m src.acquire --source MODIS_SP --start 2024-03-01 --end 2024-03-15
```

Options: `--chunk-days` (1–5, default 5), `--sleep` between calls (default 0.5 s), `--no-skip-existing` to force re-download.

Prefer `*_SP` (standard processing) sources for historical archives; `*_NRT` is aimed at recent data.

This module only fetches and saves detections. Cleaning and aggregation live in `src/compute`.
