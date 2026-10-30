#!/usr/bin/env python3
"""Run the full offline pipeline on the synthetic FIRMS fixture (no API key).

Synthetic CSV → clean → weekly grid → baseline → critical periods → JSON export.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.compute.baseline import build_baseline_and_scores  # noqa: E402
from src.compute.clean import load_and_clean  # noqa: E402
from src.compute.critical import (  # noqa: E402
    build_critical_summary,
    export_demo_calendar_json,
)
from src.compute.grid import DEFAULT_CELL_DEG, aggregate_weekly_cell_days  # noqa: E402
from src.compute.provenance import (  # noqa: E402
    build_provenance,
    write_provenance_sidecar,
)

DEFAULT_INPUT = ROOT / "demo_fixtures" / "synthetic_firms_bangladesh.csv"
DEFAULT_OUT_DIR = ROOT / "cache" / "offline_repro"
DEFAULT_JSON = DEFAULT_OUT_DIR / "offline_calendar.json"
DEFAULT_PREFIX = "offline"


def run_offline_pipeline(
    *,
    input_csv: Path = DEFAULT_INPUT,
    out_dir: Path = DEFAULT_OUT_DIR,
    json_path: Path = DEFAULT_JSON,
    prefix: str = DEFAULT_PREFIX,
    min_years: int = 2,
    top_n: int = 5,
    min_confidence: float = 0.0,
    cell_deg: float = DEFAULT_CELL_DEG,
) -> Path:
    if not input_csv.is_file():
        raise FileNotFoundError(f"Input not found: {input_csv}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_csv.stem

    cleaned = load_and_clean(
        input_csv, sensor="VIIRS_SNPP_NRT", min_confidence=min_confidence
    )
    weekly = aggregate_weekly_cell_days(cleaned, cell_deg=cell_deg)

    cleaned_path = out_dir / f"{stem}_cleaned.csv"
    weekly_path = out_dir / f"{stem}_weekly_cells.csv"
    cleaned.to_csv(cleaned_path, index=False)
    weekly.to_csv(weekly_path, index=False)

    regional, baseline, scored = build_baseline_and_scores(weekly, min_years=min_years)
    critical, peaks = build_critical_summary(baseline, scored, top_n=top_n)

    regional_path = out_dir / f"{prefix}_weekly_totals.csv"
    baseline_path = out_dir / f"{prefix}_week_of_year_baseline.csv"
    scored_path = out_dir / f"{prefix}_weekly_scored.csv"
    critical_path = out_dir / f"{prefix}_critical_periods.csv"
    peaks_path = out_dir / f"{prefix}_peak_timing.csv"

    regional.to_csv(regional_path, index=False)
    baseline.to_csv(baseline_path, index=False)
    scored.to_csv(scored_path, index=False)
    critical.to_csv(critical_path, index=False)
    peaks.to_csv(peaks_path, index=False)

    years = sorted({int(y) for y in scored["iso_year"].unique()})
    meta = {
        "title": "Cauchy's Comet: The Burning Activity Calendar",
        "region": "Bangladesh (synthetic demonstration)",
        "sensor": "VIIRS_SNPP_NRT",
        "window": "Dates present in demo_fixtures/synthetic_firms_bangladesh.csv",
        "years": years,
        "status": (
            "Synthetic offline pipeline output for local testing only. "
            "Not NASA observations; not a validated fire product."
        ),
        "data_credit": "Synthetic demo fixture (not NASA observations)",
    }
    provenance = build_provenance(
        input_path=input_csv,
        detections=cleaned,
        firms_source="VIIRS_SNPP_NRT",
        data_classification="synthetic",
        min_confidence=min_confidence,
        cell_deg=cell_deg,
        min_years=min_years,
        top_n=top_n,
        region_name="bangladesh",
        calibration_applied=False,
        repo_root=ROOT,
    )
    write_provenance_sidecar(provenance, out_dir / f"{prefix}_provenance.json")
    export_demo_calendar_json(
        baseline=baseline,
        scored=scored,
        critical=critical,
        peaks=peaks,
        out_path=json_path,
        meta=meta,
        provenance=provenance,
    )
    return json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline reproducible pipeline using the synthetic FIRMS fixture."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Synthetic FIRMS CSV (default: demo_fixtures/synthetic_firms_bangladesh.csv)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory (default: cache/offline_repro)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="JSON export path (default: <out-dir>/offline_calendar.json)",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--min-years", type=int, default=2)
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args(argv)

    json_path = args.json or (args.out_dir / "offline_calendar.json")
    try:
        written = run_offline_pipeline(
            input_csv=args.input,
            out_dir=args.out_dir,
            json_path=json_path,
            prefix=args.prefix,
            min_years=args.min_years,
            top_n=args.top_n,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Offline pipeline failed: {exc}", file=sys.stderr)
        return 1

    print(f"Offline pipeline complete.\nJSON: {written}\nOutputs: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
