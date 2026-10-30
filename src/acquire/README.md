# Data acquisition

Download NASA FIRMS active-fire CSV for the Bangladesh demonstration area.

**Status:** Implemented and tested (HTTP mocked in pytest; optional live smoke download).

## Setup

1. Create a free [FIRMS MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/map_key).
2. Copy `.env.example` to `.env` and set `FIRMS_MAP_KEY`.
3. From the repo root:

```text
pip install -r requirements.txt
```

## Supported FIRMS Area API products

| Product ID | Satellite / instrument | Type |
|------------|------------------------|------|
| `MODIS_NRT` | MODIS (Terra and Aqua combined) | NRT |
| `MODIS_SP` | MODIS (Terra and Aqua combined) | Standard archive |
| `VIIRS_SNPP_NRT` | VIIRS Suomi-NPP | NRT |
| `VIIRS_SNPP_SP` | VIIRS Suomi-NPP | Standard archive |
| `VIIRS_NOAA20_NRT` | VIIRS NOAA-20 (JPSS-1) | NRT |
| `VIIRS_NOAA20_SP` | VIIRS NOAA-20 (JPSS-1) | Standard archive |
| `VIIRS_NOAA21_NRT` | VIIRS NOAA-21 (JPSS-2) | NRT |
| `VIIRS_NOAA21_SP` | VIIRS NOAA-21 (JPSS-2) | Standard archive |

The FIRMS Area API exposes one MODIS stream (not separate Terra vs Aqua downloads). Metadata is defined in `src/acquire/products.py`.

## Directory layout (gitignored under `cache/`)

| Path | Role |
|------|------|
| `cache/raw/` | Original FIRMS CSV downloads (never overwritten by merge) |
| `cache/raw/chunks/` | Batch raw chunk files |
| `cache/merged/` | Concatenated CSV (derived; raw chunks preserved) |
| `cache/manifests/` | Acquisition manifest JSON (no MAP_KEY) |

Compute outputs remain separate under `cache/` from `src/compute` (cleaned / weekly files).

## Single window (1–5 days)

```text
python -m src.acquire --source VIIRS_SNPP_NRT --days 3
python -m src.acquire --source MODIS_SP --days 1 --date 2024-03-04 --out cache/raw/modis_bd.csv
```

Writes `{raw}.acquisition.json` beside the raw file unless `--no-manifest`.

## Historical batch (date range)

The Area API allows only 1–5 days per request. Batch mode walks the range in non-overlapping chunks, saves each under `cache/raw/chunks/`, merges successful chunks to `cache/merged/`, and writes a manifest.

```text
python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
```

Options: `--chunk-days` (1–5), `--sleep`, `--no-skip-existing`, `--no-manifest`.

Failed chunks are recorded in the manifest (`failed_chunks`) for retry; they are **not** treated as zero fire activity.

## Optional one-day smoke download (real NASA data)

Requires your MAP_KEY in `.env` (never printed):

```text
python -m src.acquire --smoke --source VIIRS_SNPP_SP --date 2024-03-04
```

Downloads one day for Bangladesh to `cache/raw/` and writes an acquisition manifest.

## Reliability

- Explicit HTTP timeouts, bounded retries with exponential backoff on transient errors.
- HTTP 200 responses are validated as CSV (API error text is rejected).
- Empty header-only CSV is allowed (zero detections).
- MAP_KEY is not included in manifests or redacted error snippets.

Cleaning and aggregation live in `src/compute`.
