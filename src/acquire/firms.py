"""NASA FIRMS Area API client for active-fire CSV downloads.

API docs: https://firms.modaps.eosdis.nasa.gov/api/area/
MAP_KEY signup: https://firms.modaps.eosdis.nasa.gov/api/map_key
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

import requests
from requests.exceptions import RequestException, Timeout

from .products import redact_secrets

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

DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0

# Retry transient server/rate-limit errors only.
RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})
PERMANENT_HTTP_STATUS = frozenset({400, 401, 403, 404, 405, 410})


class FIRMSDownloadError(RuntimeError):
    """Raised when a FIRMS download or response validation fails."""


@dataclass(frozen=True)
class DownloadResponse:
    """Validated FIRMS CSV payload and row statistics."""

    text: str
    data_row_count: int
    header_present: bool
    empty_dataset: bool


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


def build_redacted_request_label(
    source: str,
    area_coordinates: str,
    day_range: int,
    date: Optional[str] = None,
) -> str:
    """Human-readable request description without credentials."""
    date_part = date if date else "most_recent"
    return (
        f"FIRMS Area CSV source={source} area={area_coordinates} "
        f"day_range={day_range} start_date={date_part}"
    )


def count_csv_data_rows(csv_text: str) -> int:
    lines = [line for line in csv_text.splitlines() if line.strip()]
    return max(0, len(lines) - 1)


def validate_firms_csv_content(text: str, *, map_key: str = "") -> DownloadResponse:
    """Validate FIRMS CSV body; allow header-only empty datasets."""
    stripped = text.strip()
    if not stripped:
        return DownloadResponse(
            text="",
            data_row_count=0,
            header_present=False,
            empty_dataset=True,
        )

    lines = stripped.splitlines()
    first_line = lines[0]
    lower = first_line.lower()
    if "latitude" in lower and "," in first_line:
        rows = max(0, len(lines) - 1)
        return DownloadResponse(
            text=text,
            data_row_count=rows,
            header_present=True,
            empty_dataset=rows == 0,
        )

    snippet = redact_secrets(text[:400], map_key)
    if any(token in stripped.lower()[:300] for token in ("invalid", "error", "denied", "unauthorized")):
        raise FIRMSDownloadError(
            "FIRMS Area API returned an error message instead of CSV. "
            f"Response begins with: {snippet!r}"
        )
    raise FIRMSDownloadError(
        "FIRMS Area API did not return a CSV header (expected a latitude column). "
        f"Response begins with: {snippet!r}"
    )


def requested_date_range(
    *,
    chunk_start: Optional[date] = None,
    day_range: int = 1,
) -> dict[str, Optional[str]]:
    """Inclusive FIRMS Area API window for a request."""
    if chunk_start is None:
        return {"start": None, "end": None, "day_range": day_range}
    end = chunk_start.toordinal() + day_range - 1
    end_date = date.fromordinal(end)
    return {
        "start": chunk_start.isoformat(),
        "end": end_date.isoformat(),
        "day_range": day_range,
    }


def _http_get_with_retries(
    url: str,
    *,
    map_key: str,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    session: requests.Session,
    http_get: Optional[Callable[..., requests.Response]] = None,
) -> requests.Response:
    get = http_get or session.get
    attempt = 0
    last_error: Optional[Exception] = None

    while attempt <= max_retries:
        try:
            response = get(url, timeout=timeout_seconds)
        except Timeout as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(backoff_seconds * (2**attempt))
            attempt += 1
            continue
        except RequestException as exc:
            raise FIRMSDownloadError(
                "Network error while contacting FIRMS Area API "
                f"(attempt {attempt + 1}/{max_retries + 1})."
            ) from exc

        status = response.status_code
        if status in PERMANENT_HTTP_STATUS:
            raise FIRMSDownloadError(
                f"FIRMS Area API returned HTTP {status} (non-retryable). "
                "Check product id, date range, and MAP_KEY permissions."
            )
        if status in RETRYABLE_HTTP_STATUS:
            last_error = FIRMSDownloadError(f"FIRMS Area API returned HTTP {status}.")
            if attempt >= max_retries:
                break
            time.sleep(backoff_seconds * (2**attempt))
            attempt += 1
            continue
        if status >= 400:
            raise FIRMSDownloadError(
                f"FIRMS Area API returned unexpected HTTP {status}."
            )
        return response

    raise FIRMSDownloadError(
        "FIRMS Area API request failed after "
        f"{max_retries + 1} attempt(s). Check connectivity or try again later."
    ) from last_error


def download_area_csv(
    map_key: str,
    source: str,
    area_coordinates: str,
    day_range: int = 1,
    date: Optional[str] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    session: Optional[requests.Session] = None,
    http_get: Optional[Callable[..., requests.Response]] = None,
) -> str:
    """Download FIRMS Area CSV text for the given parameters."""
    url = build_area_url(map_key, source, area_coordinates, day_range, date)
    owns_session = session is None
    session = session or requests.Session()
    try:
        response = _http_get_with_retries(
            url,
            map_key=map_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            session=session,
            http_get=http_get,
        )
        response.raise_for_status()
        validated = validate_firms_csv_content(response.text, map_key=map_key)
        return validated.text
    except requests.HTTPError as exc:
        raise FIRMSDownloadError(
            "FIRMS Area API HTTP error after a successful transport response."
        ) from exc
    finally:
        if owns_session:
            session.close()


def save_csv(text: str, path: Path, *, overwrite: bool = False) -> Path:
    """Write CSV text to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing raw file: {path}. "
            "Remove the file or choose a new path."
        )
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
