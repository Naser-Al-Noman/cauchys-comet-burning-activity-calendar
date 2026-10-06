"""NASA FIRMS Area API client for active-fire CSV downloads.

API docs: https://firms.modaps.eosdis.nasa.gov/api/area/
MAP_KEY signup: https://firms.modaps.eosdis.nasa.gov/api/map_key
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

FIRMS_AREA_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Common FIRMS Area API source codes (NRT = near real-time; SP = standard processing).
FIRMS_SOURCES = (
    "MODIS_NRT",
    "MODIS_SP",
    "VIIRS_SNPP_NRT",
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA20_SP",
    "VIIRS_NOAA21_NRT",
    "VIIRS_NOAA21_SP",
)


def build_area_url(
    map_key: str,
    source: str,
    area_coordinates: str,
    day_range: int,
    date: Optional[str] = None,
) -> str:
    """Build a FIRMS Area CSV URL.

    day_range must be 1–5. If date (YYYY-MM-DD) is set, returns that start day
    through day_range days; otherwise returns the most recent day_range days.
    """
    if day_range < 1 or day_range > 5:
        raise ValueError("day_range must be between 1 and 5 (FIRMS Area API limit)")
    if source not in FIRMS_SOURCES:
        raise ValueError(
            f"Unknown source {source!r}. Expected one of: {', '.join(FIRMS_SOURCES)}"
        )

    parts = [
        FIRMS_AREA_BASE,
        quote(map_key, safe=""),
        quote(source, safe=""),
        quote(area_coordinates, safe=","),
        str(day_range),
    ]
    if date is not None:
        parts.append(quote(date, safe="-"))
    return "/".join(parts)


def download_area_csv(
    map_key: str,
    source: str,
    area_coordinates: str,
    day_range: int = 1,
    date: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> str:
    """Download FIRMS Area CSV text for the given parameters."""
    url = build_area_url(map_key, source, area_coordinates, day_range, date)
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    text = response.text
    # FIRMS returns plain-text errors with HTTP 200 in some failure cases.
    first_line = text.splitlines()[0] if text.strip() else ""
    if first_line and "latitude" not in first_line.lower() and "," not in first_line:
        raise RuntimeError(f"FIRMS Area API did not return CSV. Response: {text[:300]!r}")
    return text


def save_csv(text: str, path: Path) -> Path:
    """Write CSV text to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
