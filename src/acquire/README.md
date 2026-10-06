# Data acquisition

Download NASA FIRMS active-fire CSV for the Bangladesh demonstration area.

## Setup

1. Create a free [FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key).
2. Copy `.env.example` to `.env` and set `FIRMS_MAP_KEY`.
3. From the repo root:

```text
pip install -r requirements.txt
```

## Usage

```text
python -m src.acquire --source VIIRS_SNPP_NRT --days 3
python -m src.acquire --source MODIS_SP --days 5 --date 2024-01-01 --out cache/modis_bd.csv
```

Outputs go under `cache/` by default (gitignored). The Area API allows only 1–5 days per request.

This module only fetches and saves detections. Cleaning, aggregation, and harmonization will live in `src/compute` later.
