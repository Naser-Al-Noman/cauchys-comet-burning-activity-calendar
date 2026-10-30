"""Batch FIRMS Area downloads over a date range (max 5 days per request)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from src.compute.provenance import sha256_file

from .firms import (
    FIRMSDownloadError,
    count_csv_data_rows,
    download_area_csv,
    requested_date_range,
    save_csv,
)
from .manifest import build_batch_acquisition_manifest, write_acquisition_manifest
from .products import redact_secrets


@dataclass(frozen=True)
class ChunkResult:
    start: date
    end: date
    day_range: int
    path: Optional[Path]
    rows: int
    skipped: bool = False
    status: str = "success"
    error: Optional[str] = None
    requested_range: dict = field(default_factory=dict)
    retrieval_timestamp: Optional[str] = None


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
    and shortened for the final partial window. Chunks do not overlap and leave
    no gaps between consecutive windows.
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


def chunk_end_date(chunk_start: date, day_range: int) -> date:
    return chunk_start + timedelta(days=day_range - 1)


def covered_dates(start: date, end: date, chunk_days: int = 5) -> list[date]:
    """Expand iter_chunk_starts to the list of calendar days covered."""
    days: list[date] = []
    for chunk_start, day_range in iter_chunk_starts(start, end, chunk_days):
        for offset in range(day_range):
            days.append(chunk_start + timedelta(days=offset))
    return days


def merge_csv_files(paths: list[Path], out_path: Path, *, overwrite: bool = False) -> int:
    """Concatenate CSV chunks sharing one header. Returns data row count.

    Writes a new merged file; does not modify raw chunk files.
    """
    if out_path.exists() and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing merged file: {out_path}"
        )

    header: Optional[str] = None
    rows: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
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


def _chunk_record(result: ChunkResult, map_key: str) -> dict:
    record = {
        "chunk_start": result.start.isoformat(),
        "chunk_end": result.end.isoformat(),
        "day_range": result.day_range,
        "requested_date_range": result.requested_range,
        "retrieval_timestamp": result.retrieval_timestamp,
        "status": result.status,
        "data_row_count": result.rows,
        "error": redact_secrets(result.error or "", map_key) or None,
        "raw_file": None,
    }
    if result.path is not None and result.path.is_file():
        record["raw_file"] = {
            "path": str(result.path.as_posix()),
            "sha256": sha256_file(result.path),
            "role": "raw_firms_csv_chunk",
        }
    if map_key and record.get("error") and map_key in str(record["error"]):
        raise ValueError("chunk record leaked MAP_KEY")
    return record


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
    bbox: Optional[dict] = None,
    write_manifest: bool = True,
    manifest_path: Optional[Path] = None,
    http_get=None,
) -> tuple[list[ChunkResult], Optional[Path], dict]:
    """Download FIRMS CSV in chunks; merge successful raw chunks only.

    Returns (chunk_results, merged_path_or_none, manifest_dict).
    """
    chunk_dir = out_dir / "raw" / "chunks" / f"{region_name}_{source}_{start.isoformat()}_{end.isoformat()}"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    results: list[ChunkResult] = []
    successful_paths: list[Path] = []
    chunk_records: list[dict] = []

    for chunk_start, day_range in iter_chunk_starts(start, end, chunk_days):
        chunk_end = chunk_end_date(chunk_start, day_range)
        filename = (
            f"{region_name}_{source}_{chunk_start.isoformat()}_"
            f"{chunk_end.isoformat()}_{day_range}d.csv"
        )
        path = chunk_dir / filename
        req_range = requested_date_range(chunk_start=chunk_start, day_range=day_range)
        retrieval_ts = datetime.now(timezone.utc).isoformat()

        if skip_existing and path.is_file() and path.stat().st_size > 0:
            rows = count_csv_data_rows(path.read_text(encoding="utf-8"))
            result = ChunkResult(
                start=chunk_start,
                end=chunk_end,
                day_range=day_range,
                path=path,
                rows=rows,
                skipped=True,
                status="skipped_existing",
                requested_range=req_range,
                retrieval_timestamp=retrieval_ts,
            )
            results.append(result)
            successful_paths.append(path)
            chunk_records.append(_chunk_record(result, map_key))
            continue

        try:
            csv_text = download_area_csv(
                map_key=map_key,
                source=source,
                area_coordinates=area_coordinates,
                day_range=day_range,
                date=chunk_start.isoformat(),
                http_get=http_get,
            )
            save_csv(csv_text, path, overwrite=False)
            rows = count_csv_data_rows(csv_text)
            result = ChunkResult(
                start=chunk_start,
                end=chunk_end,
                day_range=day_range,
                path=path,
                rows=rows,
                skipped=False,
                status="success",
                requested_range=req_range,
                retrieval_timestamp=retrieval_ts,
            )
            results.append(result)
            successful_paths.append(path)
            chunk_records.append(_chunk_record(result, map_key))
        except (FIRMSDownloadError, FileExistsError, OSError) as exc:
            result = ChunkResult(
                start=chunk_start,
                end=chunk_end,
                day_range=day_range,
                path=None,
                rows=0,
                skipped=False,
                status="failed",
                error=str(exc),
                requested_range=req_range,
                retrieval_timestamp=retrieval_ts,
            )
            results.append(result)
            chunk_records.append(_chunk_record(result, map_key))

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    merged_path: Optional[Path] = None
    merged_rows = 0
    if successful_paths:
        merged_path = (
            out_dir
            / "merged"
            / f"{region_name}_{source}_{start.isoformat()}_{end.isoformat()}_merged.csv"
        )
        try:
            merged_rows = merge_csv_files(successful_paths, merged_path, overwrite=False)
        except FileExistsError:
            merged_path = None

    failed_count = sum(1 for r in results if r.status == "failed")
    if failed_count:
        status = "partial_failure" if successful_paths else "failed"
    else:
        status = "success"

    manifest = build_batch_acquisition_manifest(
        source=source,
        area_name=region_name,
        bbox=bbox or {},
        requested_start=start.isoformat(),
        requested_end=end.isoformat(),
        retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
        chunk_records=chunk_records,
        merged_path=merged_path,
        merged_row_count=merged_rows,
        status=status,
        map_key=map_key,
    )

    if write_manifest:
        path = manifest_path or (
            out_dir
            / "manifests"
            / f"{region_name}_{source}_{start.isoformat()}_{end.isoformat()}_acquisition.json"
        )
        write_acquisition_manifest(manifest, path)
        manifest = dict(manifest)
        manifest["manifest_path"] = str(path.as_posix())

    return results, merged_path, manifest
