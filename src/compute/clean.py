"""Load and clean FIRMS-style detection CSVs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .confidence import harmonize_confidence

REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date", "confidence")


def infer_sensor(source: str | None, path: Path | None = None) -> str:
    """Infer MODIS vs VIIRS from a FIRMS source code or filename."""
    text = " ".join(part for part in (source or "", path.name if path else "")).lower()
    if "viirs" in text:
        return "VIIRS"
    if "modis" in text:
        return "MODIS"
    raise ValueError(
        "Could not infer sensor. Pass --source (e.g. MODIS_SP or VIIRS_SNPP_NRT)."
    )


def clean_detections(
    df: pd.DataFrame,
    *,
    sensor: str,
    min_confidence: float = 0.0,
) -> pd.DataFrame:
    """Drop invalid rows/duplicates and attach shared confidence.

    Rules:
    - require latitude, longitude, acq_date, confidence
    - coerce types; drop rows with missing coords/date/confidence
    - drop exact duplicate point-days (lat, lon, acq_date, acq_time if present)
    - keep rows with confidence_shared >= min_confidence
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV missing columns: {', '.join(missing)}")

    out = df.copy()
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["acq_date"] = pd.to_datetime(out["acq_date"], errors="coerce").dt.normalize()
    out["confidence_shared"] = harmonize_confidence(out["confidence"], sensor)
    out["sensor"] = sensor.upper()

    out = out.dropna(subset=["latitude", "longitude", "acq_date", "confidence_shared"])
    out = out[
        (out["latitude"].between(-90, 90))
        & (out["longitude"].between(-180, 180))
        & (out["confidence_shared"] >= min_confidence)
    ]

    dedupe_cols = ["latitude", "longitude", "acq_date"]
    if "acq_time" in out.columns:
        dedupe_cols.append("acq_time")
    out = out.drop_duplicates(subset=dedupe_cols)

    return out.reset_index(drop=True)


def load_and_clean(
    path: Path,
    *,
    sensor: str | None = None,
    min_confidence: float = 0.0,
) -> pd.DataFrame:
    """Read a FIRMS CSV and return cleaned detections."""
    resolved_sensor = infer_sensor(sensor, path)
    df = pd.read_csv(path)
    return clean_detections(df, sensor=resolved_sensor, min_confidence=min_confidence)
