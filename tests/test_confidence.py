from __future__ import annotations

import pandas as pd
import pytest

from src.compute.confidence import VIIRS_CONFIDENCE_MAP, harmonize_confidence


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("l", 0.3),
        ("n", 0.6),
        ("h", 0.9),
        ("low", 0.3),
        ("nominal", 0.6),
        ("high", 0.9),
    ],
)
def test_viirs_confidence_mapping(raw: str, expected: float) -> None:
    series = pd.Series([raw])
    out = harmonize_confidence(series, "VIIRS_SNPP_NRT")
    assert out.iloc[0] == pytest.approx(expected)


def test_modis_confidence_scales_to_unit_interval() -> None:
    series = pd.Series([0, 50, 100, 150])
    out = harmonize_confidence(series, "MODIS_SP")
    assert out.tolist() == pytest.approx([0.0, 0.5, 1.0, 1.0])


def test_unknown_viirs_confidence_becomes_nan() -> None:
    series = pd.Series(["x"])
    out = harmonize_confidence(series, "VIIRS")
    assert pd.isna(out.iloc[0])


def test_documented_viirs_map_keys() -> None:
    assert set(VIIRS_CONFIDENCE_MAP) >= {"l", "n", "h", "low", "nominal", "high"}
