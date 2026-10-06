"""Quantile-map MODIS weekly cell activity to VIIRS (planned method step 3).

Fits empirical quantile mapping on overlapping cell-weeks, separately by
meteorological season when enough pairs exist. This is scaffolding for
harmonization — not a validated accuracy claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

JOIN_KEYS = ("iso_year", "iso_week", "cell_x", "cell_y")


def assign_season(week_start: pd.Series) -> pd.Series:
    """Bangladesh-oriented seasons from week_start month.

    - dry: Nov–Feb
    - pre_monsoon: Mar–May
    - monsoon: Jun–Oct
    """
    month = pd.to_datetime(week_start).dt.month
    season = pd.Series(index=week_start.index, dtype="object")
    season = season.mask(month.isin([11, 12, 1, 2]), "dry")
    season = season.mask(month.isin([3, 4, 5]), "pre_monsoon")
    season = season.mask(month.isin([6, 7, 8, 9, 10]), "monsoon")
    return season


def empirical_quantile_map(
    source: np.ndarray,
    reference: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    """Map `values` from the source distribution onto the reference distribution."""
    source = np.asarray(source, dtype=float)
    reference = np.asarray(reference, dtype=float)
    values = np.asarray(values, dtype=float)
    if source.size == 0 or reference.size == 0:
        raise ValueError("source and reference must be non-empty for quantile mapping")

    src_sorted = np.sort(source)
    ref_sorted = np.sort(reference)
    # Percentile ranks of training source values in [0, 1].
    src_ranks = np.linspace(0.0, 1.0, num=src_sorted.size)
    # For each value, interpolate its rank in the source ECDF, then the ref quantile.
    value_ranks = np.interp(values, src_sorted, src_ranks, left=0.0, right=1.0)
    ref_ranks = np.linspace(0.0, 1.0, num=ref_sorted.size)
    return np.interp(value_ranks, ref_ranks, ref_sorted)


@dataclass
class QuantileMapModel:
    """Per-season (and optional global fallback) quantile maps."""

    by_season: dict[str, tuple[np.ndarray, np.ndarray]]
    global_pair: Optional[tuple[np.ndarray, np.ndarray]]
    min_pairs: int = 20

    def transform(self, values: np.ndarray, seasons: np.ndarray) -> np.ndarray:
        out = np.full(values.shape, np.nan, dtype=float)
        for season in np.unique(seasons):
            mask = seasons == season
            pair = self.by_season.get(str(season))
            if pair is None:
                pair = self.global_pair
            if pair is None:
                continue
            src, ref = pair
            out[mask] = empirical_quantile_map(src, ref, values[mask])
        # Any remaining NaN (unknown season / no model): leave unmapped as NaN.
        return out


def build_overlap_table(
    modis_weekly: pd.DataFrame,
    viirs_weekly: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join weekly cell tables on space-time keys."""
    left = modis_weekly.copy()
    right = viirs_weekly.copy()
    for frame, name in ((left, "modis"), (right, "viirs")):
        missing = [k for k in JOIN_KEYS if k not in frame.columns]
        if missing:
            raise ValueError(f"{name} weekly table missing columns: {', '.join(missing)}")
        if "active_cell_days" not in frame.columns:
            raise ValueError(f"{name} weekly table missing active_cell_days")

    left = left[list(JOIN_KEYS) + ["active_cell_days", "week_start"]].rename(
        columns={"active_cell_days": "modis_active_cell_days"}
    )
    right = right[list(JOIN_KEYS) + ["active_cell_days"]].rename(
        columns={"active_cell_days": "viirs_active_cell_days"}
    )
    merged = left.merge(right, on=list(JOIN_KEYS), how="inner")
    merged["season"] = assign_season(merged["week_start"])
    return merged


def fit_quantile_map(
    overlap: pd.DataFrame,
    *,
    min_pairs: int = 20,
) -> QuantileMapModel:
    """Fit season-specific maps when each season has at least min_pairs rows."""
    if overlap.empty:
        raise ValueError("No overlapping MODIS/VIIRS cell-weeks to fit calibration")

    by_season: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for season, group in overlap.groupby("season"):
        if len(group) < min_pairs:
            continue
        by_season[str(season)] = (
            group["modis_active_cell_days"].to_numpy(dtype=float),
            group["viirs_active_cell_days"].to_numpy(dtype=float),
        )

    global_pair = (
        overlap["modis_active_cell_days"].to_numpy(dtype=float),
        overlap["viirs_active_cell_days"].to_numpy(dtype=float),
    )
    return QuantileMapModel(by_season=by_season, global_pair=global_pair, min_pairs=min_pairs)


def apply_modis_calibration(
    modis_weekly: pd.DataFrame,
    model: QuantileMapModel,
) -> pd.DataFrame:
    """Add calibrated_active_cell_days to a MODIS weekly cell table."""
    out = modis_weekly.copy()
    if "week_start" not in out.columns:
        raise ValueError("modis_weekly must include week_start")
    seasons = assign_season(out["week_start"]).to_numpy()
    values = out["active_cell_days"].to_numpy(dtype=float)
    out["season"] = seasons
    out["calibrated_active_cell_days"] = model.transform(values, seasons)
    out["calibration"] = "quantile_map_to_viirs"
    return out


def calibrate_modis_to_viirs(
    modis_weekly: pd.DataFrame,
    viirs_weekly: pd.DataFrame,
    *,
    min_pairs: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, QuantileMapModel]:
    """Fit on overlap and return (overlap_table, calibrated_modis, model)."""
    overlap = build_overlap_table(modis_weekly, viirs_weekly)
    model = fit_quantile_map(overlap, min_pairs=min_pairs)
    calibrated = apply_modis_calibration(modis_weekly, model)
    return overlap, calibrated, model


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Quantile-map MODIS weekly cells to VIIRS on overlapping cell-weeks."
    )
    parser.add_argument("--modis-weekly", type=Path, required=True)
    parser.add_argument("--viirs-weekly", type=Path, required=True)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("cache"),
        help="Output directory (default: cache)",
    )
    parser.add_argument(
        "--min-pairs",
        type=int,
        default=20,
        help="Minimum overlap rows to fit a season-specific map (default: 20)",
    )
    args = parser.parse_args(argv)

    for path, label in (
        (args.modis_weekly, "MODIS"),
        (args.viirs_weekly, "VIIRS"),
    ):
        if not path.is_file():
            print(f"{label} weekly file not found: {path}", file=sys.stderr)
            return 1

    try:
        modis = pd.read_csv(args.modis_weekly)
        viirs = pd.read_csv(args.viirs_weekly)
        overlap, calibrated, model = calibrate_modis_to_viirs(
            modis, viirs, min_pairs=args.min_pairs
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Calibration failed: {exc}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    overlap_path = args.out_dir / "calibration_overlap_cell_weeks.csv"
    calibrated_path = args.out_dir / "modis_weekly_cells_calibrated.csv"
    overlap.to_csv(overlap_path, index=False)
    calibrated.to_csv(calibrated_path, index=False)

    seasons_fit = ", ".join(sorted(model.by_season)) or "(none; global fallback only)"
    print(
        f"Overlap cell-weeks: {len(overlap)}\n"
        f"Season-specific maps: {seasons_fit}\n"
        f"Wrote {overlap_path}\n"
        f"Wrote {calibrated_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
