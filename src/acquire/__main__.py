"""CLI: download NASA FIRMS detections for a planned region.

Requires FIRMS_MAP_KEY in the environment or a local .env file.

Examples:
  python -m src.acquire --source VIIRS_SNPP_NRT --days 3
  python -m src.acquire --source MODIS_SP --days 5 --date 2024-01-01 --out cache/modis.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

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
        help="Day range 1–5 (FIRMS limit)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Optional start date YYYY-MM-DD (historical window)",
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
        help="Output CSV path (default: cache/<region>_<source>_<days>d.csv)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env containing FIRMS_MAP_KEY",
    )
    args = parser.parse_args(argv)

    _load_dotenv(args.env_file)
    map_key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not map_key:
        print(
            "FIRMS_MAP_KEY is not set. Request a free key at "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key "
            "and put it in .env (see .env.example).",
            file=sys.stderr,
        )
        return 1

    region = BANGLADESH_BBOX
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
