from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.compute.clean import clean_detections, load_and_clean
from src.compute.grid import DEFAULT_CELL_DEG, aggregate_weekly_cell_days


def test_synthetic_fixture_drops_exact_duplicate_row(synthetic_firms_csv: Path) -> None:
    raw = pd.read_csv(synthetic_firms_csv)
    assert len(raw) == 6
    cleaned = load_and_clean(synthetic_firms_csv, sensor="VIIRS_SNPP_NRT")
    assert len(cleaned) == 5
    assert cleaned.duplicated(subset=["latitude", "longitude", "acq_date", "acq_time"]).sum() == 0


def test_clean_rejects_missing_required_columns() -> None:
    df = pd.DataFrame({"latitude": [1.0], "longitude": [2.0]})
    with pytest.raises(ValueError, match="missing columns"):
        clean_detections(df, sensor="VIIRS")


def test_empty_detections_after_filter_returns_empty_weekly_frame() -> None:
    df = pd.DataFrame(
        {
            "latitude": [999.0],
            "longitude": [90.0],
            "acq_date": ["2024-03-04"],
            "confidence": ["n"],
        }
    )
    cleaned = clean_detections(df, sensor="VIIRS")
    weekly = aggregate_weekly_cell_days(cleaned)
    assert len(cleaned) == 0
    assert list(weekly.columns) == [
        "iso_year",
        "iso_week",
        "week_start",
        "cell_x",
        "cell_y",
        "cell_lon_center",
        "cell_lat_center",
        "active_cell_days",
        "sensor",
    ]
    assert len(weekly) == 0


def test_weekly_aggregation_counts_cell_days_once(synthetic_firms_csv: Path) -> None:
    cleaned = load_and_clean(synthetic_firms_csv, sensor="VIIRS_SNPP_NRT")
    weekly = aggregate_weekly_cell_days(cleaned, cell_deg=DEFAULT_CELL_DEG)

    assert weekly["active_cell_days"].eq(1).all()
    assert int(weekly["active_cell_days"].sum()) == 3
    assert set(weekly["iso_week"].astype(int).tolist()) == {10}
    assert int(weekly["iso_year"].iloc[0]) == 2024


def test_iso_week_and_week_start_from_synthetic_dates() -> None:
    cleaned = pd.DataFrame(
        {
            "latitude": [23.81],
            "longitude": [90.41],
            "acq_date": pd.to_datetime(["2024-03-04"]),
            "sensor": ["VIIRS"],
        }
    )
    weekly = aggregate_weekly_cell_days(cleaned)
    row = weekly.iloc[0]
    assert int(row["iso_year"]) == 2024
    assert int(row["iso_week"]) == 10
    assert pd.Timestamp(row["week_start"]).date().isoformat() == "2024-03-04"
