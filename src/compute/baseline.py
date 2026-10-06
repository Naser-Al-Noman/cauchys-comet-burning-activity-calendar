"""Week-of-year baselines and anomaly scores (planned method step 4).

Builds regional (Bangladesh-wide) baselines from multi-year weekly cell tables.
This is analysis scaffolding — not a validated climate or fire-risk product.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _activity_column(df: pd.DataFrame) -> str:
    if "calibrated_active_cell_days" in df.columns:
        return "calibrated_active_cell_days"
    if "active_cell_days" in df.columns:
        return "active_cell_days"
    raise ValueError(
        "Weekly table needs active_cell_days or calibrated_active_cell_days"
    )


def regional_weekly_totals(weekly_cells: pd.DataFrame) -> pd.DataFrame:
    """Sum cell activity to one Bangladesh-wide value per ISO year-week."""
    required = {"iso_year", "iso_week", "week_start"}
    missing = required - set(weekly_cells.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    value_col = _activity_column(weekly_cells)
    work = weekly_cells.copy()
    work["week_start"] = pd.to_datetime(work["week_start"]).dt.normalize()
    work["_value"] = pd.to_numeric(work[value_col], errors="coerce").fillna(0.0)

    out = (
        work.groupby(["iso_year", "iso_week"], as_index=False)
        .agg(
            week_start=("week_start", "min"),
            regional_active_cell_days=("_value", "sum"),
            n_active_cells=("_value", "size"),
        )
        .sort_values(["iso_year", "iso_week"])
        .reset_index(drop=True)
    )
    return out


def load_weekly_tables(paths: list[Path]) -> pd.DataFrame:
    """Concatenate one or more weekly cell CSVs."""
    frames = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        frames.append(pd.read_csv(path))
    if not frames:
        raise ValueError("No weekly input files provided")
    return pd.concat(frames, ignore_index=True)


def build_week_of_year_baseline(
    regional: pd.DataFrame,
    *,
    min_years: int = 2,
) -> pd.DataFrame:
    """Percentile baseline per ISO week across years.

    Returns one row per iso_week with p10/p50/p90 and years_used.
    Weeks with fewer than min_years observations are still reported but flagged.
    """
    if regional.empty:
        raise ValueError("regional weekly table is empty")

    rows = []
    for iso_week, group in regional.groupby("iso_week"):
        values = group["regional_active_cell_days"].to_numpy(dtype=float)
        years = group["iso_year"].nunique()
        rows.append(
            {
                "iso_week": int(iso_week),
                "years_used": int(years),
                "n_samples": int(len(values)),
                "p10": float(np.percentile(values, 10)),
                "p50": float(np.percentile(values, 50)),
                "p90": float(np.percentile(values, 90)),
                "mean": float(np.mean(values)),
                "enough_years": years >= min_years,
            }
        )
    return pd.DataFrame(rows).sort_values("iso_week").reset_index(drop=True)


def anomaly_score(value: float, p10: float, p50: float, p90: float) -> float:
    """Signed anomaly vs median, scaled by the p10–p90 half-range.

    0 ≈ typical; positive = above median; negative = below. If the percentile
    band is zero width, returns 0 when equal to the median else ±1.
    """
    half = 0.5 * (p90 - p10)
    if half <= 0:
        if value > p50:
            return 1.0
        if value < p50:
            return -1.0
        return 0.0
    return float((value - p50) / half)


def score_regional_weeks(
    regional: pd.DataFrame,
    baseline: pd.DataFrame,
) -> pd.DataFrame:
    """Attach baseline percentiles and anomaly_score to each regional week."""
    out = regional.merge(baseline, on="iso_week", how="left")
    out["anomaly_score"] = [
        anomaly_score(v, p10, p50, p90)
        for v, p10, p50, p90 in zip(
            out["regional_active_cell_days"],
            out["p10"],
            out["p50"],
            out["p90"],
            strict=True,
        )
    ]
    # Percentile rank of this week among historical same iso_week samples.
    ranks = []
    by_week = {
        int(w): g["regional_active_cell_days"].to_numpy(dtype=float)
        for w, g in regional.groupby("iso_week")
    }
    for _, row in out.iterrows():
        hist = by_week[int(row["iso_week"])]
        ranks.append(float((hist <= row["regional_active_cell_days"]).mean()))
    out["percentile_rank"] = ranks
    return out


def build_baseline_and_scores(
    weekly_cells: pd.DataFrame,
    *,
    min_years: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (regional_weekly, baseline, scored_weeks)."""
    regional = regional_weekly_totals(weekly_cells)
    baseline = build_week_of_year_baseline(regional, min_years=min_years)
    scored = score_regional_weeks(regional, baseline)
    return regional, baseline, scored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build week-of-year regional baselines and anomaly scores."
    )
    parser.add_argument(
        "--weekly",
        type=Path,
        nargs="+",
        required=True,
        help="One or more weekly cell CSV paths (multi-year)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("cache"),
        help="Output directory (default: cache)",
    )
    parser.add_argument(
        "--min-years",
        type=int,
        default=2,
        help="Flag weeks with fewer than this many years in the baseline",
    )
    parser.add_argument(
        "--prefix",
        default="regional",
        help="Output filename prefix (default: regional)",
    )
    args = parser.parse_args(argv)

    try:
        weekly = load_weekly_tables(args.weekly)
        regional, baseline, scored = build_baseline_and_scores(
            weekly, min_years=args.min_years
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Baseline failed: {exc}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    regional_path = args.out_dir / f"{args.prefix}_weekly_totals.csv"
    baseline_path = args.out_dir / f"{args.prefix}_week_of_year_baseline.csv"
    scored_path = args.out_dir / f"{args.prefix}_weekly_scored.csv"
    regional.to_csv(regional_path, index=False)
    baseline.to_csv(baseline_path, index=False)
    scored.to_csv(scored_path, index=False)

    n_weeks = baseline["iso_week"].nunique()
    n_years = regional["iso_year"].nunique()
    flagged = int((~baseline["enough_years"]).sum())
    print(
        f"Years in record: {n_years}\n"
        f"ISO weeks with baseline: {n_weeks} ({flagged} below min_years={args.min_years})\n"
        f"Wrote {regional_path}\n"
        f"Wrote {baseline_path}\n"
        f"Wrote {scored_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
