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

## Deploy on Vercel

No backend is required. Host this folder as a static site:

1. Import the GitHub repo in Vercel.
2. Set **Root Directory** to `web`.
3. Leave **Build Command** empty; **Output Directory** can stay default / `.`.

[`vercel.json`](vercel.json) enables clean URLs and short caching for `/data/*`.

Do not add `FIRMS_MAP_KEY` or Python acquire/compute as Vercel serverless for this demo — refresh `data/demo_calendar.json` locally (or in CI) and commit when you want the public site updated.
