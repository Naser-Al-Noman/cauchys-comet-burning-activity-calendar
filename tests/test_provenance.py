from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.run_offline_pipeline import run_offline_pipeline
from src.compute.provenance import (
    PROVENANCE_SCHEMA_VERSION,
    build_provenance,
    infer_data_classification,
    provenance_contains_sensitive_values,
    sha256_file,
    stable_provenance_id,
)
from tests.helpers import assert_frontend_json_contract, load_json

REQUIRED_PROVENANCE_KEYS = (
    "schema_version",
    "dataset_identifier",
    "provenance_id",
    "satellite_instrument",
    "observation_date_range",
    "geographic_processing_area",
    "input_file",
    "processing_configuration",
    "confidence_filter",
    "grid_resolution_deg",
    "temporal_aggregation",
    "calibration",
    "baseline_methodology",
    "pipeline_version",
    "git_commit",
    "generated_at",
    "data_classification",
)


def test_sha256_file_matches_hashlib(synthetic_firms_csv: Path) -> None:
    expected = hashlib.sha256(synthetic_firms_csv.read_bytes()).hexdigest()
    assert sha256_file(synthetic_firms_csv) == expected


def test_infer_synthetic_classification(synthetic_firms_csv: Path) -> None:
    assert infer_data_classification(synthetic_firms_csv) == "synthetic"


def test_infer_real_classification_from_cache_path() -> None:
    path = Path("cache/bangladesh_VIIRS_SNPP_NRT_recent_3d.csv")
    assert infer_data_classification(path) == "real_firms_csv"


def test_stable_provenance_id_is_deterministic() -> None:
    config = {"min_confidence_shared": 0.0, "cell_deg": 0.05}
    a = stable_provenance_id(
        input_sha256="abc", pipeline_version="0.2.0", processing_configuration=config
    )
    b = stable_provenance_id(
        input_sha256="abc", pipeline_version="0.2.0", processing_configuration=config
    )
    assert a == b


def test_build_provenance_includes_required_fields(synthetic_firms_csv: Path) -> None:
    prov = build_provenance(
        input_path=synthetic_firms_csv,
        firms_source="VIIRS_SNPP_NRT",
        data_classification="synthetic",
    )
    for key in REQUIRED_PROVENANCE_KEYS:
        assert key in prov
    assert prov["schema_version"] == PROVENANCE_SCHEMA_VERSION
    assert prov["data_classification"] == "synthetic"
    assert prov["input_file"]["sha256"] == sha256_file(synthetic_firms_csv)
    assert prov["calibration"]["status"] == "not_applied"
    assert provenance_contains_sensitive_values(prov) is False


def test_build_provenance_missing_optional_fields_are_null() -> None:
    prov = build_provenance(
        input_path=None,
        input_sha256=None,
        detections=None,
        firms_source=None,
    )
    assert prov["satellite_instrument"] is None
    assert prov["observation_date_range"] is None
    assert prov["input_file"] is None
    assert prov["data_classification"] is None
    assert prov["git_commit"] is None or isinstance(prov["git_commit"], str)


def test_offline_pipeline_json_backward_compatible_and_provenance(
    repo_root: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "prov_out"
    json_path = run_offline_pipeline(
        input_csv=repo_root / "demo_fixtures" / "synthetic_firms_bangladesh.csv",
        out_dir=out_dir,
        json_path=out_dir / "offline_calendar.json",
        prefix="offline",
    )
    payload = load_json(json_path)
    assert_frontend_json_contract(payload)
    meta = payload["meta"]
    assert "title" in meta
    assert "years" in meta
    assert "status" in meta
    assert "data_credit" in meta
    prov = meta["provenance"]
    for key in REQUIRED_PROVENANCE_KEYS:
        assert key in prov
    assert prov["data_classification"] == "synthetic"
    assert "Synthetic" in meta["status"]
    assert "NASA observations" in meta["status"] or "not NASA" in meta["status"].lower()
    sidecar = out_dir / "offline_provenance.json"
    assert sidecar.is_file()
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["provenance_id"] == prov["provenance_id"]


def test_exported_provenance_has_no_credentials(synthetic_firms_csv: Path, tmp_path: Path) -> None:
    prov = build_provenance(
        input_path=synthetic_firms_csv,
        data_classification="synthetic",
    )
    blob = json.dumps(prov)
    assert "FIRMS_MAP_KEY" not in blob
    assert provenance_contains_sensitive_values(prov) is False
