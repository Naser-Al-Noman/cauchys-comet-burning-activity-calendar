# Data sources and repository status

This document lists datasets the project uses or plans to use, and what is **actually present in the repository** today.

Status labels match [docs/method.md](method.md): **Implemented and tested**, **Implemented but experimental**, **Planned but not implemented**, **Not yet validated**.

## Active fire detections — NASA FIRMS

| Component | Status |
|-----------|--------|
| FIRMS Area API download (`src/acquire`) | **Implemented and tested** (network tests optional; client logic in repo) |
| MODIS + VIIRS source codes in CLI | **Implemented and tested** |
| Committed raw FIRMS archives in git | **Not in repo** — real downloads go to gitignored `cache/` |

**Real observations:** CSV files produced by `python -m src.acquire` using a valid `FIRMS_MAP_KEY`. Classification in provenance metadata: `real_firms_csv`. Each download can write an **acquisition manifest** JSON under `cache/manifests/` (or beside a single raw file) with product id, bbox, date range, SHA-256 of raw files, chunk status, and failed-chunk records — never the MAP_KEY.

**Synthetic demonstration:** `demo_fixtures/synthetic_firms_bangladesh.csv` — FIRMS-*shaped* rows for pipeline testing only. Classification: `synthetic`. **Not NASA data** and must not be cited as fire statistics.

## Validation and context datasets

| Dataset | Status |
|---------|--------|
| MODIS MCD64A1 (burned area) | **Planned but not implemented** — no ingestion or comparison scripts |
| NASA POWER (meteorology) | **Planned but not implemented** |
| NASA GIBS (imagery / basemap) | **Planned but not implemented** |

## Geographic scope

- **Processing area (implemented default):** Bangladesh bounding box in `src/acquire/regions.py` (west 88.0°, south 20.5°, east 92.7°, north 26.7°).
- **Broader ROI (South Asia):** **Planned** — only Bangladesh is wired in acquire/compute CLIs today.

## Committed vs generated artifacts

| Artifact | Type | Notes |
|----------|------|--------|
| `demo_fixtures/synthetic_firms_bangladesh.csv` | Synthetic input | Used by pytest and `scripts/run_offline_pipeline.py` |
| `cache/offline_repro/*` | Generated (gitignored) | Offline synthetic pipeline outputs + provenance sidecar |
| `web/data/demo_calendar.json` | Real-process concept extract | March-only VIIRS-oriented demo; separate from synthetic offline JSON |

Provenance fields (`meta.provenance` in JSON exports) record input SHA-256, processing configuration, and `data_classification` so outputs can be traced without exposing API keys.

## Challenge timeline

Dataset choices and FIRMS product versions may change after the official NASA Space Apps 2026 challenge text is finalized. Update this document when requirements are locked.

## Validation limitations (current)

- No independent burned-area validation has been run.
- No multi-sensor harmonized archive is published in the repository.
- Synthetic and real paths must stay clearly labeled in metadata and documentation.
