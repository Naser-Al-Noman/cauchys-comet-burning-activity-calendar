"""Structured acquisition manifests for FIRMS downloads."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.compute.provenance import sha256_file

from .products import FIRMSProductInfo, product_info, redact_secrets

ACQUISITION_MANIFEST_SCHEMA = "1.0.0"


def acquisition_id(*, product_id: str, area: str, request_key: str) -> str:
    """Stable identifier for an acquisition run (no secrets in inputs)."""
    payload = f"{product_id}|{area}|{request_key}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bbox_dict(west: float, south: float, east: float, north: float, name: str) -> dict:
    return {
        "name": name,
        "west": west,
        "south": south,
        "east": east,
        "north": north,
    }


def _product_block(info: FIRMSProductInfo) -> dict[str, Any]:
    return {
        "product_id": info.product_id,
        "satellite_instrument": info.satellite_instrument,
        "product_type": info.product_type,
        "notes": info.notes,
    }


def build_single_acquisition_manifest(
    *,
    source: str,
    area_name: str,
    bbox: dict[str, Any],
    requested_range: dict[str, Any],
    retrieval_timestamp: str,
    raw_path: Path,
    row_count: int,
    status: str,
    dataset_identifier: Optional[str] = None,
    failed_chunks: Optional[list[dict]] = None,
    map_key: str = "",
) -> dict[str, Any]:
    info = product_info(source)
    file_sha = sha256_file(raw_path) if raw_path.is_file() else None
    acq_id = acquisition_id(
        product_id=source,
        area=area_name,
        request_key=json.dumps(requested_range, sort_keys=True),
    )
    manifest = {
        "schema_version": ACQUISITION_MANIFEST_SCHEMA,
        "acquisition_id": acq_id,
        "dataset_identifier": dataset_identifier or f"ccc-firms-acq-{acq_id[:16]}",
        "product": _product_block(info),
        "geographic_bbox": bbox,
        "requested_date_range": requested_range,
        "retrieval_timestamp": retrieval_timestamp,
        "download_status": status,
        "raw_file": {
            "path": str(raw_path.as_posix()),
            "sha256": file_sha,
            "data_row_count": row_count,
            "role": "raw_firms_csv",
        },
        "merged_file": None,
        "failed_chunks": failed_chunks or [],
        "api_metadata": {
            "endpoint": "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
            "area_api_day_range_limit": 5,
        },
    }
    _assert_manifest_has_no_secrets(manifest, map_key)
    return manifest


def build_batch_acquisition_manifest(
    *,
    source: str,
    area_name: str,
    bbox: dict[str, Any],
    requested_start: str,
    requested_end: str,
    retrieval_timestamp: str,
    chunk_records: list[dict[str, Any]],
    merged_path: Optional[Path],
    merged_row_count: int,
    status: str,
    map_key: str = "",
) -> dict[str, Any]:
    info = product_info(source)
    request_key = f"{requested_start}:{requested_end}"
    acq_id = acquisition_id(product_id=source, area=area_name, request_key=request_key)
    failed = [c for c in chunk_records if c.get("status") == "failed"]
    manifest = {
        "schema_version": ACQUISITION_MANIFEST_SCHEMA,
        "acquisition_id": acq_id,
        "dataset_identifier": f"ccc-firms-acq-{acq_id[:16]}",
        "product": _product_block(info),
        "geographic_bbox": bbox,
        "requested_date_range": {
            "start": requested_start,
            "end": requested_end,
        },
        "retrieval_timestamp": retrieval_timestamp,
        "download_status": status,
        "chunks": chunk_records,
        "failed_chunks": failed,
        "merged_file": None,
        "api_metadata": {
            "endpoint": "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
            "area_api_day_range_limit": 5,
        },
    }
    if merged_path is not None and merged_path.is_file():
        manifest["merged_file"] = {
            "path": str(merged_path.as_posix()),
            "sha256": sha256_file(merged_path),
            "data_row_count": merged_row_count,
            "role": "merged_firms_csv",
        }
    _assert_manifest_has_no_secrets(manifest, map_key)
    return manifest


def write_acquisition_manifest(manifest: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _assert_manifest_has_no_secrets(manifest: dict[str, Any], map_key: str) -> None:
    blob = json.dumps(manifest)
    for marker in ("FIRMS_MAP_KEY", "MAP_KEY="):
        if marker in blob:
            raise ValueError("Manifest must not contain credential markers")
    # Short keys can appear coincidentally inside SHA-256 hex digests.
    if map_key and len(map_key) >= 20 and map_key in blob:
        raise ValueError("Manifest must not contain MAP_KEY")
