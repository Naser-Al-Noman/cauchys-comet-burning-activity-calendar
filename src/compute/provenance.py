"""Build structured provenance metadata for calendar JSON exports."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd

from src.acquire.regions import BANGLADESH_BBOX
from src.compute.grid import DEFAULT_CELL_DEG

PROVENANCE_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "0.2.0-module2"

DataClassification = Literal["synthetic", "real_firms_csv"]

_SENSITIVE_SUBSTRINGS = (
    "FIRMS_MAP_KEY",
    "MAP_KEY=",
    "api_key",
    "password",
    "secret",
    "token",
)


def sha256_file(path: Path, *, chunk_size: int = 65536) -> str:
    """Return hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def try_git_commit(repo_root: Optional[Path] = None) -> Optional[str]:
    """Return current git commit hash, or null if unavailable."""
    root = repo_root or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def infer_data_classification(
    input_path: Optional[Path],
    *,
    explicit: Optional[DataClassification] = None,
) -> Optional[DataClassification]:
    if explicit is not None:
        return explicit
    if input_path is None:
        return None
    parts = {part.lower() for part in input_path.parts}
    name = input_path.name.lower()
    if "synthetic" in name or (parts & {"demo_fixtures"} and "synthetic" in name):
        return "synthetic"
    if parts & {"cache", "demo_fixtures"} and "synthetic" not in name:
        # cache/ downloads are real FIRMS CSVs when acquired via src.acquire
        if parts & {"cache"}:
            return "real_firms_csv"
    return None


def observation_date_range_from_detections(
    detections: Optional[pd.DataFrame],
) -> Optional[dict[str, Optional[str]]]:
    if detections is None or detections.empty or "acq_date" not in detections.columns:
        return None
    dates = pd.to_datetime(detections["acq_date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return {
        "start": dates.min().date().isoformat(),
        "end": dates.max().date().isoformat(),
    }


def stable_provenance_id(
    *,
    input_sha256: Optional[str],
    pipeline_version: str,
    processing_configuration: dict[str, Any],
) -> str:
    """Deterministic ID for the same input hash and processing configuration."""
    payload = {
        "input_sha256": input_sha256,
        "pipeline_version": pipeline_version,
        "processing_configuration": processing_configuration,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def geographic_processing_area(
    region_name: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if region_name is None or region_name == "bangladesh":
        return {
            "name": BANGLADESH_BBOX.name,
            "bbox_west": BANGLADESH_BBOX.west,
            "bbox_south": BANGLADESH_BBOX.south,
            "bbox_east": BANGLADESH_BBOX.east,
            "bbox_north": BANGLADESH_BBOX.north,
        }
    return None


def _input_path_for_provenance(
    input_path: Path, repo_root: Optional[Path] = None
) -> str:
    resolved = input_path.resolve()
    if repo_root is not None:
        try:
            return resolved.relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            pass
    return resolved.as_posix()


def build_provenance(
    *,
    input_path: Optional[Path] = None,
    input_sha256: Optional[str] = None,
    detections: Optional[pd.DataFrame] = None,
    firms_source: Optional[str] = None,
    data_classification: Optional[DataClassification] = None,
    min_confidence: float = 0.0,
    cell_deg: float = DEFAULT_CELL_DEG,
    min_years: int = 2,
    top_n: int = 5,
    region_name: str = "bangladesh",
    calibration_applied: bool = False,
    calibration_method: Optional[str] = None,
    repo_root: Optional[Path] = None,
    pipeline_stages: Optional[list[str]] = None,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Assemble provenance metadata; use null for unknown fields."""
    if input_path is not None and input_sha256 is None:
        input_sha256 = sha256_file(input_path)

    classification = infer_data_classification(
        input_path, explicit=data_classification
    )

    processing_configuration: dict[str, Any] = {
        "firms_source": firms_source,
        "region_name": region_name,
        "min_confidence_shared": min_confidence,
        "cell_deg": cell_deg,
        "min_years_baseline": min_years,
        "critical_top_n": top_n,
        "pipeline_stages": pipeline_stages
        or [
            "clean_detections",
            "aggregate_weekly_cell_days",
            "regional_weekly_totals",
            "week_of_year_baseline",
            "anomaly_score",
            "critical_periods",
            "peak_timing",
        ],
    }

    provenance_id = stable_provenance_id(
        input_sha256=input_sha256,
        pipeline_version=PIPELINE_VERSION,
        processing_configuration=processing_configuration,
    )

    if calibration_applied:
        cal_status = "applied"
        cal_method = calibration_method or "quantile_map_to_viirs_by_season"
    else:
        cal_status = "not_applied"
        cal_method = calibration_method

    when = generated_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    input_trace = None
    if input_path is not None:
        input_trace = {
            "path": _input_path_for_provenance(input_path, repo_root),
            "sha256": input_sha256,
        }

    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "dataset_identifier": f"ccc-burn-cal-{provenance_id[:16]}",
        "provenance_id": provenance_id,
        "satellite_instrument": firms_source,
        "observation_date_range": observation_date_range_from_detections(detections),
        "geographic_processing_area": geographic_processing_area(region_name),
        "input_file": input_trace,
        "processing_configuration": processing_configuration,
        "confidence_filter": {
            "min_confidence_shared": min_confidence,
            "harmonization": "MODIS 0-100 scaled to 0-1; VIIRS l/n/h mapped to 0.3/0.6/0.9",
        },
        "grid_resolution_deg": cell_deg,
        "temporal_aggregation": {
            "method": "ISO calendar week",
            "cell_day_rule": "At most one active cell-day per grid cell per calendar day",
        },
        "calibration": {
            "status": cal_status,
            "method": cal_method,
        },
        "baseline_methodology": (
            "Regional sum of weekly active cell-days; week-of-year p10/p50/p90 "
            "across available years; anomaly score vs in-sample baseline (not held-out)."
        ),
        "pipeline_version": PIPELINE_VERSION,
        "git_commit": try_git_commit(repo_root),
        "generated_at": when.isoformat(),
        "data_classification": classification,
    }


def provenance_contains_sensitive_values(provenance: dict[str, Any]) -> bool:
    """Return True if serialized provenance appears to contain credential-like text."""
    text = json.dumps(provenance).lower()
    return any(marker.lower() in text for marker in _SENSITIVE_SUBSTRINGS)


def write_provenance_sidecar(provenance: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return path
