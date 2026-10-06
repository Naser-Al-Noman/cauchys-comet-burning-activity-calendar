"""Aggregate cleaned detections to weekly ~5.5 km cells (cell-day once)."""

from __future__ import annotations

import pandas as pd

# ~5.5 km near the equator (1 deg ≈ 111 km → 5.5/111 ≈ 0.05 deg).
DEFAULT_CELL_DEG = 0.05


def _cell_index(coord: pd.Series, cell_deg: float) -> pd.Series:
    return (coord / cell_deg).floordiv(1).astype("int64")


def aggregate_weekly_cell_days(
    detections: pd.DataFrame,
    *,
    cell_deg: float = DEFAULT_CELL_DEG,
) -> pd.DataFrame:
    """Count unique cell-days per week on a fixed lon/lat grid.

    Each (cell_x, cell_y, calendar day) contributes at most 1, regardless of how
    many raw detections fall in that cell that day. Weeks use ISO week
    (year, week) derived from acq_date.
    """
    required = {"latitude", "longitude", "acq_date"}
    missing = required - set(detections.columns)
    if missing:
        raise ValueError(f"Detections missing columns: {', '.join(sorted(missing))}")
    if cell_deg <= 0:
        raise ValueError("cell_deg must be positive")

    if detections.empty:
        return pd.DataFrame(
            columns=[
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
        )

    work = detections.copy()
    work["acq_date"] = pd.to_datetime(work["acq_date"]).dt.normalize()
    work["cell_x"] = _cell_index(work["longitude"], cell_deg)
    work["cell_y"] = _cell_index(work["latitude"], cell_deg)

    iso = work["acq_date"].dt.isocalendar()
    work["iso_year"] = iso.year.astype("int64")
    work["iso_week"] = iso.week.astype("int64")
    # Monday of the ISO week.
    work["week_start"] = work["acq_date"] - pd.to_timedelta(
        work["acq_date"].dt.weekday, unit="D"
    )

    cell_days = work.drop_duplicates(subset=["cell_x", "cell_y", "acq_date"])

    group_cols = ["iso_year", "iso_week", "week_start", "cell_x", "cell_y"]
    if "sensor" in cell_days.columns:
        group_cols = ["sensor", *group_cols]

    weekly = (
        cell_days.groupby(group_cols, as_index=False)
        .size()
        .rename(columns={"size": "active_cell_days"})
    )
    weekly["cell_lon_center"] = (weekly["cell_x"] + 0.5) * cell_deg
    weekly["cell_lat_center"] = (weekly["cell_y"] + 0.5) * cell_deg
    weekly["cell_deg"] = cell_deg

    return weekly.sort_values(group_cols).reset_index(drop=True)
