"""CLI: download NASA FIRMS detections for a planned region.

Requires FIRMS_MAP_KEY in the environment or a local .env file.

Examples:
  python -m src.acquire --source VIIRS_SNPP_NRT --days 3
  python -m src.acquire --source MODIS_SP --days 5 --date 2024-01-01 --out cache/raw/modis.csv
  python -m src.acquire --source VIIRS_SNPP_SP --start 2024-03-01 --end 2024-03-15
  python -m src.acquire --smoke --source VIIRS_SNPP_SP --date 2024-03-04
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .batch import download_date_range, parse_iso_date
from .firms import (
    FIRMS_SOURCES,
    build_redacted_request_label,
    count_csv_data_rows,
    download_area_csv,
    requested_date_range,
    save_csv,
)
from .manifest import build_single_acquisition_manifest, write_acquisition_manifest
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


def _bbox_manifest_dict(region) -> dict:
    return {
        "name": region.name,
        "west": region.west,
        "south": region.south,
        "east": region.east,
        "north": region.north,
    }


def run_single_download(
    *,
    map_key: str,
    source: str,
    region,
    day_range: int,
    date: str | None,
    out: Path,
    write_manifest: bool = True,
) -> tuple[Path, dict]:
    csv_text = download_area_csv(
        map_key=map_key,
        source=source,
        area_coordinates=region.as_firms_area(),
        day_range=day_range,
        date=date,
    )
    save_csv(csv_text, out, overwrite=False)
    rows = count_csv_data_rows(csv_text)
    chunk_start = parse_iso_date(date) if date else None
    req = requested_date_range(
        chunk_start=chunk_start,
        day_range=day_range,
    )
    manifest = build_single_acquisition_manifest(
        source=source,
        area_name=region.name,
        bbox=_bbox_manifest_dict(region),
        requested_range=req,
        retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
        raw_path=out,
        row_count=rows,
        status="success",
        map_key=map_key,
    )
    if write_manifest:
        manifest_path = out.with_suffix(".acquisition.json")
        write_acquisition_manifest(manifest, manifest_path)
        manifest = dict(manifest)
        manifest["manifest_path"] = str(manifest_path.as_posix())
    return out, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download NASA FIRMS active-fire CSV for the Bangladesh demo area."
    )
    parser.add_argument(
        "--source",
        choices=FIRMS_SOURCES,
        help="FIRMS Area API source code",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Optional one-day Bangladesh smoke download (requires MAP_KEY)",
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
        "--no-manifest",
        action="store_true",
        help="Do not write acquisition manifest JSON",
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
        help="Single-request raw CSV path (ignored in batch mode)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("cache"),
        help="Batch output directory (default: cache)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env containing FIRMS_MAP_KEY",
    )
    args = parser.parse_args(argv)

    if args.smoke:
        args.source = args.source or "VIIRS_SNPP_SP"
        args.days = 1
        if not args.date:
            print("--smoke requires --date YYYY-MM-DD", file=sys.stderr)
            return 1

    if not args.source:
        print("--source is required (or use --smoke with --date).", file=sys.stderr)
        return 1

    if (args.start is None) ^ (args.end is None):
        print("Provide both --start and --end for batch mode.", file=sys.stderr)
        return 1

    map_key = _require_map_key(args.env_file)
    region = BANGLADESH_BBOX

    if args.start is not None and args.end is not None:
        try:
            start = parse_iso_date(args.start)
            end = parse_iso_date(args.end)
            results, merged, manifest = download_date_range(
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
                bbox=_bbox_manifest_dict(region),
                write_manifest=not args.no_manifest,
            )
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            print(f"Batch download failed: {exc}", file=sys.stderr)
            return 1

        fetched = sum(1 for r in results if r.status == "success")
        skipped = sum(1 for r in results if r.status == "skipped_existing")
        failed = sum(1 for r in results if r.status == "failed")
        total_rows = sum(r.rows for r in results if r.status != "failed")
        print(
            f"Chunks: {len(results)} ({fetched} downloaded, {skipped} skipped, {failed} failed)\n"
            f"Chunk detection rows (sum, non-failed): {total_rows}\n"
            f"Download status: {manifest.get('download_status')}\n"
            f"Merged file: {merged}\n"
            f"Manifest: {manifest.get('manifest_path', '(not written)')}"
        )
        return 1 if manifest.get("download_status") == "failed" else 0

    out = args.out
    if out is None:
        stamp = args.date.replace("-", "") if args.date else "recent"
        out = Path("cache") / "raw" / f"{region.name}_{args.source}_{stamp}_{args.days}d.csv"

    try:
        out_path, manifest = run_single_download(
            map_key=map_key,
            source=args.source,
            region=region,
            day_range=args.days,
            date=args.date,
            out=out,
            write_manifest=not args.no_manifest,
        )
    except FileExistsError as exc:
        print(f"{exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        label = build_redacted_request_label(
            args.source, region.as_firms_area(), args.days, args.date
        )
        print(f"Download failed ({label}): {exc}", file=sys.stderr)
        return 1

    rows = count_csv_data_rows(out_path.read_text(encoding="utf-8"))
    print(
        f"Wrote raw file: {out_path} ({rows} detection rows)\n"
        f"Manifest: {manifest.get('manifest_path', '(not written)')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
