from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

FRONTEND_JSON_KEYS = (
    "meta",
    "baseline",
    "weeks",
    "critical_periods",
    "peak_timing",
)


def assert_no_nan_or_inf(obj: Any, path: str = "root") -> None:
    """Recursively fail if any float is NaN or infinite."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert_no_nan_or_inf(value, f"{path}.{key}")
        return
    if isinstance(obj, list):
        for index, value in enumerate(obj):
            assert_no_nan_or_inf(value, f"{path}[{index}]")
        return
    if isinstance(obj, float):
        assert not math.isnan(obj), f"NaN at {path}"
        assert math.isfinite(obj), f"Non-finite at {path}"
        return
    if obj is None:
        return


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_frontend_json_contract(payload: dict) -> None:
    for key in FRONTEND_JSON_KEYS:
        assert key in payload, f"Missing top-level key: {key}"
    assert isinstance(payload["meta"], dict)
    for section in ("baseline", "weeks", "critical_periods", "peak_timing"):
        assert isinstance(payload[section], list)
    assert_no_nan_or_inf(payload)
