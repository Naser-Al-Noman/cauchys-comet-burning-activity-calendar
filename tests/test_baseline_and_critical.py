from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.compute.baseline import (
    anomaly_score,
    build_baseline_and_scores,
    build_week_of_year_baseline,
    regional_weekly_totals,
    score_regional_weeks,
)
from src.compute.critical import (
    build_critical_summary,
    export_demo_calendar_json,
    rank_critical_periods,
)
from src.compute.clean import load_and_clean
from src.compute.grid import aggregate_weekly_cell_days
from tests.helpers import assert_frontend_json_contract, assert_no_nan_or_inf


def _weekly_from_synthetic(synthetic_firms_csv: Path) -> pd.DataFrame:
    cleaned = load_and_clean(synthetic_firms_csv, sensor="VIIRS_SNPP_NRT")
    return aggregate_weekly_cell_days(cleaned)


def test_regional_weekly_total_matches_cell_day_sum(synthetic_firms_csv: Path) -> None:
    weekly = _weekly_from_synthetic(synthetic_firms_csv)
    regional = regional_weekly_totals(weekly)
    assert len(regional) == 1
    assert int(regional.iloc[0]["regional_active_cell_days"]) == 3


def test_anomaly_score_at_median_is_zero() -> None:
    assert anomaly_score(10.0, 5.0, 10.0, 15.0) == pytest.approx(0.0)


def test_anomaly_score_above_median_is_positive() -> None:
    assert anomaly_score(15.0, 5.0, 10.0, 15.0) > 0


def test_baseline_and_scores_on_synthetic_single_year(synthetic_firms_csv: Path) -> None:
    weekly = _weekly_from_synthetic(synthetic_firms_csv)
    regional, baseline, scored = build_baseline_and_scores(weekly, min_years=2)

    assert len(baseline) == 1
    assert int(baseline.iloc[0]["iso_week"]) == 10
    assert not bool(baseline.iloc[0]["enough_years"])
    assert len(scored) == 1
    assert scored.iloc[0]["anomaly_score"] == pytest.approx(0.0)
    assert scored.iloc[0]["percentile_rank"] == pytest.approx(1.0)
    assert_no_nan_or_inf(scored.to_dict(orient="records"))


def test_multi_year_baseline_percentiles_from_controlled_values() -> None:
    regional = pd.DataFrame(
        {
            "iso_year": [2020, 2021, 2022],
            "iso_week": [10, 10, 10],
            "week_start": ["2020-03-02", "2021-03-08", "2022-03-07"],
            "regional_active_cell_days": [10.0, 20.0, 30.0],
        }
    )
    baseline = build_week_of_year_baseline(regional, min_years=2)
    row = baseline.iloc[0]
    assert int(row["iso_week"]) == 10
    assert row["p50"] == pytest.approx(20.0)
    assert row["p10"] == pytest.approx(12.0)
    assert row["p90"] == pytest.approx(28.0)
    assert bool(row["enough_years"]) is True

    scored = score_regional_weeks(regional, baseline)
    middle = scored[scored["iso_year"] == 2021].iloc[0]
    assert middle["anomaly_score"] == pytest.approx(0.0)


def test_critical_ranking_orders_by_median_activity() -> None:
    baseline = pd.DataFrame(
        {
            "iso_week": [9, 10, 11],
            "p50": [100.0, 300.0, 200.0],
            "enough_years": [True, True, True],
        }
    )
    ranked = rank_critical_periods(baseline, top_n=2)
    assert ranked["critical_rank"].tolist() == [1, 2]
    assert ranked["iso_week"].tolist() == [10, 11]


def test_json_export_matches_frontend_contract(tmp_path: Path, synthetic_firms_csv: Path) -> None:
    weekly = _weekly_from_synthetic(synthetic_firms_csv)
    _, baseline, scored = build_baseline_and_scores(weekly, min_years=2)
    critical, peaks = build_critical_summary(baseline, scored, top_n=3)
    out_path = tmp_path / "offline_calendar.json"
    meta = {
        "title": "Test",
        "region": "Synthetic",
        "sensor": "VIIRS_SNPP_NRT",
        "window": "Synthetic fixture",
        "years": [2024],
        "status": "Synthetic offline test export.",
        "data_credit": "Synthetic demo fixture (not NASA observations)",
    }
    export_demo_calendar_json(
        baseline=baseline,
        scored=scored,
        critical=critical,
        peaks=peaks,
        out_path=out_path,
        meta=meta,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert_frontend_json_contract(payload)
    assert payload["meta"]["data_credit"].startswith("Synthetic")
