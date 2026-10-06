"""CLI: clean FIRMS CSV detections and aggregate to weekly cell-days.

Examples:
  python -m src.compute --input demo_fixtures/synthetic_firms_bangladesh.csv --source VIIRS_SNPP_NRT
  python -m src.compute --input cache/bangladesh_VIIRS_SNPP_NRT_recent_3d.csv --source VIIRS_SNPP_NRT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clean import load_and_clean
from .grid import DEFAULT_CELL_DEG, aggregate_weekly_cell_days


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clean FIRMS detections and aggregate to a weekly ~5.5 km grid."
    )
    parser.add_argument("--input", type=Path, required=True, help="FIRMS CSV path")
    parser.add_argument(
        "--source",
        default=None,
        help="FIRMS source code used to infer sensor (e.g. MODIS_SP, VIIRS_SNPP_NRT)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum shared confidence 0–1 to keep (default: 0)",
    )
    parser.add_argument(
        "--cell-deg",
        type=float,
        default=DEFAULT_CELL_DEG,
        help=f"Grid cell size in degrees (default: {DEFAULT_CELL_DEG} ≈ 5.5 km)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("cache"),
        help="Directory for cleaned and weekly CSV outputs (default: cache)",
    )
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    try:
        cleaned = load_and_clean(
            args.input,
            sensor=args.source,
            min_confidence=args.min_confidence,
        )
        weekly = aggregate_weekly_cell_days(cleaned, cell_deg=args.cell_deg)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Compute failed: {exc}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.input.stem
    cleaned_path = args.out_dir / f"{stem}_cleaned.csv"
    weekly_path = args.out_dir / f"{stem}_weekly_cells.csv"
    cleaned.to_csv(cleaned_path, index=False)
    weekly.to_csv(weekly_path, index=False)

    print(
        f"Cleaned detections: {len(cleaned)} rows -> {cleaned_path}\n"
        f"Weekly cell aggregates: {len(weekly)} rows -> {weekly_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
