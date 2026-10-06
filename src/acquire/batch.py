"""Batch FIRMS Area downloads over a date range (max 5 days per request)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from .firms import download_area_csv, save_csv


@dataclass(frozen=True)
class ChunkResult:
    start: date
    day_range: int
    path: Path
    rows: int
    skipped: bool = False


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def iter_chunk_starts(
    start: date,
    end: date,
    chunk_days: int = 5,
) -> Iterable[tuple[date, int]]:
    """Yield (chunk_start, day_range) covering start..end inclusive.

    FIRMS returns [DATE] .. [DATE + DAY_RANGE - 1], so day_range is capped at 5
    and shortened for the final partial window.
    """
    if chunk_days < 1 or chunk_days > 5:
        raise ValueError("chunk_days must be between 1 and 5")
    if end < start:
        raise ValueError("end date must be on or after start date")

    cursor = start
    while cursor <= end:
        remaining = (end - cursor).days + 1
        day_range = min(chunk_days, remaining)
        yield cursor, day_range
        cursor = cursor + timedelta(days=day_range)


def _count_data_rows(csv_text: str) -> int:
    lines = [line for line in csv_text.splitlines() if line.strip()]
    return max(0, len(lines) - 1)


def merge_csv_files(paths: list[Path], out_path: Path) -> int:
    """Concatenate CSV chunks sharing one header. Returns data row count."""
    header: Optional[str] = None
    rows: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        if header is None:
            header = lines[0]
        elif lines[0] != header:
            raise RuntimeError(
                f"CSV header mismatch in {path}; cannot merge with {paths[0]}"
            )
        rows.extend(lines[1:])

    if header is None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("", encoding="utf-8")
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join([header, *rows])
    if rows:
        body += "\n"
    out_path.write_text(body, encoding="utf-8", newline="\n")
    return len(rows)


def download_date_range(
    *,
    map_key: str,
    source: str,
    area_coordinates: str,
    start: date,
    end: date,
    out_dir: Path,
    region_name: str = "bangladesh",
    chunk_days: int = 5,
    sleep_seconds: float = 0.5,
    skip_existing: bool = True,
) -> tuple[list[ChunkResult], Path]:
    """Download FIRMS CSV in chunks and write a merged file.

    Returns (chunk_results, merged_path).
    """
    chunk_dir = out_dir / "chunks" / f"{region_name}_{source}_{start.isoformat()}_{end.isoformat()}"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    results: list[ChunkResult] = []
    chunk_paths: list[Path] = []

    for chunk_start, day_range in iter_chunk_starts(start, end, chunk_days):
        chunk_end = chunk_start + timedelta(days=day_range - 1)
        filename = (
            f"{region_name}_{source}_{chunk_start.isoformat()}_"
            f"{chunk_end.isoformat()}_{day_range}d.csv"
        )
        path = chunk_dir / filename
        chunk_paths.append(path)

        if skip_existing and path.is_file() and path.stat().st_size > 0:
            rows = _count_data_rows(path.read_text(encoding="utf-8"))
            results.append(
                ChunkResult(
                    start=chunk_start,
                    day_range=day_range,
                    path=path,
                    rows=rows,
                    skipped=True,
                )
            )
            continue

        csv_text = download_area_csv(
            map_key=map_key,
            source=source,
            area_coordinates=area_coordinates,
            day_range=day_range,
            date=chunk_start.isoformat(),
        )
        save_csv(csv_text, path)
        results.append(
            ChunkResult(
                start=chunk_start,
                day_range=day_range,
                path=path,
                rows=_count_data_rows(csv_text),
                skipped=False,
            )
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    merged_path = (
        out_dir
        / f"{region_name}_{source}_{start.isoformat()}_{end.isoformat()}_merged.csv"
    )
    merge_csv_files(chunk_paths, merged_path)
    return results, merged_path
