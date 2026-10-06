# Web interface

Static demo for **Cauchy's Comet: The Burning Activity Calendar**.

It reads [`data/demo_calendar.json`](data/demo_calendar.json), exported from the
local VIIRS March 2020–2024 Bangladesh pipeline (concept-stage extract — not a
validated product).

## Run locally

Browsers block `fetch` from `file://`. From the repo root:

```text
python -m http.server 8080 --directory web
```

Open http://localhost:8080/

## Refresh demo JSON

```text
python -m src.compute.critical --baseline cache/viirs_march_week_of_year_baseline.csv --scored cache/viirs_march_weekly_scored.csv --prefix viirs_march --export-json web/data/demo_calendar.json
```
