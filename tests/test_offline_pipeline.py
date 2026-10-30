from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts.run_offline_pipeline import run_offline_pipeline
from tests.helpers import assert_frontend_json_contract, load_json


def test_run_offline_pipeline_produces_valid_json(repo_root: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "offline_out"
    json_path = run_offline_pipeline(
        input_csv=repo_root / "demo_fixtures" / "synthetic_firms_bangladesh.csv",
        out_dir=out_dir,
        json_path=out_dir / "offline_calendar.json",
        prefix="offline",
    )

    assert json_path.is_file()
    cleaned_path = out_dir / "synthetic_firms_bangladesh_cleaned.csv"
    weekly_path = out_dir / "synthetic_firms_bangladesh_weekly_cells.csv"
    baseline_path = out_dir / "offline_week_of_year_baseline.csv"
    scored_path = out_dir / "offline_weekly_scored.csv"
    critical_path = out_dir / "offline_critical_periods.csv"
    peaks_path = out_dir / "offline_peak_timing.csv"

    for path in (
        cleaned_path,
        weekly_path,
        baseline_path,
        scored_path,
        critical_path,
        peaks_path,
    ):
        assert path.is_file(), path

    cleaned = pd.read_csv(cleaned_path)
    assert cleaned.duplicated(subset=["latitude", "longitude", "acq_date", "acq_time"]).sum() == 0

    weekly = pd.read_csv(weekly_path)
    assert weekly["active_cell_days"].eq(1).all()

    payload = load_json(json_path)
    assert_frontend_json_contract(payload)
    assert "Synthetic" in payload["meta"]["status"]


def test_compute_cli_missing_input_exits_nonzero(repo_root: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.compute",
            "--input",
            str(repo_root / "does_not_exist.csv"),
            "--source",
            "VIIRS_SNPP_NRT",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_compute_cli_empty_csv_with_header_only(tmp_path: Path, repo_root: Path) -> None:
    empty_path = tmp_path / "empty.csv"
    empty_path.write_text(
        "latitude,longitude,acq_date,confidence\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.compute",
            "--input",
            str(empty_path),
            "--source",
            "VIIRS_SNPP_NRT",
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    weekly = pd.read_csv(out_dir / "empty_weekly_cells.csv")
    assert len(weekly) == 0
