"""Map MODIS and VIIRS confidence fields onto a shared 0–1 scale."""

from __future__ import annotations

import pandas as pd

# VIIRS categorical confidence → shared scale (documented choice for this pipeline).
VIIRS_CONFIDENCE_MAP = {
    "l": 0.3,
    "low": 0.3,
    "n": 0.6,
    "nominal": 0.6,
    "h": 0.9,
    "high": 0.9,
}


def harmonize_confidence(series: pd.Series, sensor: str) -> pd.Series:
    """Return confidence on a shared 0–1 scale.

    - MODIS: numeric 0–100 → divide by 100.
    - VIIRS: low/nominal/high (or l/n/h) → mapped values above.
    """
    sensor_key = sensor.strip().lower()
    if sensor_key.startswith("modis"):
        numeric = pd.to_numeric(series, errors="coerce")
        return (numeric / 100.0).clip(lower=0.0, upper=1.0)

    if sensor_key.startswith("viirs"):
        keys = series.astype(str).str.strip().str.lower()
        mapped = keys.map(VIIRS_CONFIDENCE_MAP)
        return mapped.astype("float64")

    raise ValueError(f"Unsupported sensor for confidence mapping: {sensor!r}")
