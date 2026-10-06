"""Rank critical burning periods and track peak-timing shifts (method step 5).

Uses regional weekly totals / baselines. Experimental scaffolding only —
not an operational warning product.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def rank_critical_periods(
    baseline: pd.DataFrame,
    *,
    top_n: int = 5,
    value_col: str = "p50",
) -> pd.DataFrame:
    """Rank ISO weeks by typical activity (default: median p50)."""
    if baseline.empty:
        raise ValueError("baseline table is empty")
    if value_col not in baseline.columns:
        raise ValueError(f"baseline missing column {value_col}")

    work = baseline.copy()
    # Prefer weeks with enough multi-year support when ranking.
    if "enough_years" in work.columns:
        eligible = work[work["enough_years"]].copy()
        if eligible.empty:
            eligible = work
    else:
        eligible = work

    ranked = eligible.sort_values(value_col, ascending=False).reset_index(drop=True)
    ranked.insert(0, "critical_rank", np.arange(1, len(ranked) + 1))
    return ranked.head(top_n).reset_index(drop=True)


def peak_timing_by_year(regional_or_scored: pd.DataFrame) -> pd.DataFrame:
    """For each year, the ISO week with maximum regional activity."""
    required = {"iso_year", "iso_week", "regional_active_cell_days"}
    missing = required - set(regional_or_scored.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    rows = []
    for year, group in regional_or_scored.groupby("iso_year"):
        idx = group["regional_active_cell_days"].idxmax()
        peak = group.loc[idx]
        rows.append(
            {
                "iso_year": int(year),
                "peak_iso_week": int(peak["iso_week"]),
                "peak_week_start": str(pd.to_datetime(peak["week_start"]).date())
                if "week_start" in group.columns
                else None,
                "peak_regional_active_cell_days": float(peak["regional_active_cell_days"]),
            }
        )
    out = pd.DataFrame(rows).sort_values("iso_year").reset_index(drop=True)
    if len(out) >= 2:
        # Simple linear slope: ISO weeks per year (descriptive only).
        x = out["iso_year"].to_numpy(dtype=float)
        y = out["peak_iso_week"].to_numpy(dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        out["peak_week_slope_per_year"] = slope
    else:
        out["peak_week_slope_per_year"] = np.nan
    return out


def build_critical_summary(
    baseline: pd.DataFrame,
    scored: pd.DataFrame,
    *,
    top_n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (critical_periods, peak_timing)."""
    critical = rank_critical_periods(baseline, top_n=top_n)
    peaks = peak_timing_by_year(scored)
    return critical, peaks


def export_demo_calendar_json(
    *,
    baseline: pd.DataFrame,
    scored: pd.DataFrame,
    critical: pd.DataFrame,
    peaks: pd.DataFrame,
    out_path: Path,
    meta: dict,
) -> Path:
    """Write a compact JSON payload for the web demo."""
    payload = {
        "meta": meta,
        "baseline": baseline.to_dict(orient="records"),
        "weeks": scored.to_dict(orient="records"),
        "critical_periods": critical.to_dict(orient="records"),
        "peak_timing": peaks.to_dict(orient="records"),
    }
    # Native JSON types
    def _convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if pd.isna(obj):
            return None
        return obj

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, default=_convert)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rank critical periods and track peak-timing shifts."
    )
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--scored", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("cache"))
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="Optional path for web demo JSON (e.g. web/data/demo_calendar.json)",
    )
    parser.add_argument("--prefix", default="regional")
    args = parser.parse_args(argv)

    try:
        baseline = pd.read_csv(args.baseline)
        scored = pd.read_csv(args.scored)
        critical, peaks = build_critical_summary(
            baseline, scored, top_n=args.top_n
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Critical-period analysis failed: {exc}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    critical_path = args.out_dir / f"{args.prefix}_critical_periods.csv"
    peaks_path = args.out_dir / f"{args.prefix}_peak_timing.csv"
    critical.to_csv(critical_path, index=False)
    peaks.to_csv(peaks_path, index=False)

    if args.export_json is not None:
        years = sorted(scored["iso_year"].unique().tolist())
        meta = {
            "title": "Cauchy's Comet: The Burning Activity Calendar",
            "region": "Bangladesh (demonstration)",
            "sensor": "VIIRS_SNPP_SP",
            "window": "March only (ISO weeks present in the extract)",
            "years": years,
            "status": (
                "Concept-stage demo extract from local pipeline runs. "
                "Not a validated product; detections are not burned area."
            ),
            "data_credit": "Data: NASA FIRMS (MODIS, VIIRS)",
        }
        export_demo_calendar_json(
            baseline=baseline,
            scored=scored,
            critical=critical,
            peaks=peaks,
            out_path=args.export_json,
            meta=meta,
        )

    slope = peaks["peak_week_slope_per_year"].iloc[0] if len(peaks) else float("nan")
    print(
        f"Critical periods: {len(critical)} -> {critical_path}\n"
        f"Peak timing years: {len(peaks)} -> {peaks_path}\n"
        f"Peak ISO-week slope (weeks/year, descriptive): {slope}"
    )
    if args.export_json is not None:
        print(f"Demo JSON: {args.export_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
