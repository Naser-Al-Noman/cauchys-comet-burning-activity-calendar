"""CLI: download NASA FIRMS detections for a planned region.

Requires FIRMS_MAP_KEY in the environment or a local .env file.

Examples:
  python -m src.acquire --source VIIRS_SNPP_NRT --days 3
  python -m src.acquire --source MODIS_SP --days 5 --date 2024-01-01 --out cache/modis.csv
  python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .batch import download_date_range, parse_iso_date
from .firms import FIRMS_SOURCES, download_area_csv, save_csv
from .regions import BANGLADESH_BBOX


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines from .env if present (no extra dependency)."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _require_map_key(env_file: Path) -> str:
    _load_dotenv(env_file)
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        print(
            "FIRMS_MAP_KEY is not set. Request a free key at "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key "
            "and put it in .env (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)
    return map_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download NASA FIRMS active-fire CSV for the Bangladesh demo area."
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=FIRMS_SOURCES,
        help="FIRMS Area API source code",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Day range 1–5 for a single request (ignored when --start/--end are set)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Optional start date YYYY-MM-DD for a single request",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Batch mode: inclusive start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Batch mode: inclusive end date YYYY-MM-DD",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=5,
        help="Batch chunk size 1–5 (default: 5)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between batch API calls (default: 0.5)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-download chunks even if the chunk file already exists",
    )
    parser.add_argument(
        "--region",
        default="bangladesh",
        choices=["bangladesh"],
        help="Named bounding box (default: bangladesh)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Single-request output CSV path (ignored in batch mode)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("cache"),
        help="Batch output directory for chunks + merged CSV (default: cache)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env containing FIRMS_MAP_KEY",
    )
    args = parser.parse_args(argv)

    if (args.start is None) ^ (args.end is None):
        print("Provide both --start and --end for batch mode.", file=sys.stderr)
        return 1

    map_key = _require_map_key(args.env_file)
    region = BANGLADESH_BBOX

    if args.start is not None and args.end is not None:
        try:
            start = parse_iso_date(args.start)
            end = parse_iso_date(args.end)
            results, merged = download_date_range(
                map_key=map_key,
                source=args.source,
                area_coordinates=region.as_firms_area(),
                start=start,
                end=end,
                out_dir=args.out_dir,
                region_name=region.name,
                chunk_days=args.chunk_days,
                sleep_seconds=args.sleep,
                skip_existing=not args.no_skip_existing,
            )
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            print(f"Batch download failed: {exc}", file=sys.stderr)
            return 1

        fetched = sum(1 for r in results if not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        total_rows = sum(r.rows for r in results)
        print(
            f"Chunks: {len(results)} ({fetched} downloaded, {skipped} skipped)\n"
            f"Chunk detection rows (sum): {total_rows}\n"
            f"Merged file: {merged}"
        )
        return 0

    out = args.out
    if out is None:
        stamp = args.date.replace("-", "") if args.date else "recent"
        out = Path("cache") / f"{region.name}_{args.source}_{stamp}_{args.days}d.csv"

    try:
        csv_text = download_area_csv(
            map_key=map_key,
            source=args.source,
            area_coordinates=region.as_firms_area(),
            day_range=args.days,
            date=args.date,
        )
        save_csv(csv_text, out)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    body_lines = [line for line in csv_text.splitlines() if line.strip()]
    n_rows = max(0, len(body_lines) - 1)
    print(f"Wrote {out} ({n_rows} detection rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
