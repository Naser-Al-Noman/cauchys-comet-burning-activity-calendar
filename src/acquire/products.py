"""FIRMS product metadata and secret redaction for acquisition manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ProductType = Literal["NRT", "SP"]


@dataclass(frozen=True)
class FIRMSProductInfo:
    """Metadata for a FIRMS Area API source code supported by this client."""

    product_id: str
    satellite_instrument: str
    product_type: ProductType
    notes: Optional[str] = None


# FIRMS Area API source codes implemented in firms.FIRMS_SOURCES.
# MODIS Area products combine Terra and Aqua detections in one stream.
FIRMS_PRODUCTS: dict[str, FIRMSProductInfo] = {
    "MODIS_NRT": FIRMSProductInfo(
        product_id="MODIS_NRT",
        satellite_instrument="MODIS (Terra and Aqua combined)",
        product_type="NRT",
        notes="Near real-time MODIS active fire",
    ),
    "MODIS_SP": FIRMSProductInfo(
        product_id="MODIS_SP",
        satellite_instrument="MODIS (Terra and Aqua combined)",
        product_type="SP",
        notes="Standard processing MODIS archive",
    ),
    "VIIRS_SNPP_NRT": FIRMSProductInfo(
        product_id="VIIRS_SNPP_NRT",
        satellite_instrument="VIIRS Suomi-NPP",
        product_type="NRT",
    ),
    "VIIRS_SNPP_SP": FIRMSProductInfo(
        product_id="VIIRS_SNPP_SP",
        satellite_instrument="VIIRS Suomi-NPP",
        product_type="SP",
    ),
    "VIIRS_NOAA20_NRT": FIRMSProductInfo(
        product_id="VIIRS_NOAA20_NRT",
        satellite_instrument="VIIRS NOAA-20 (JPSS-1)",
        product_type="NRT",
    ),
    "VIIRS_NOAA20_SP": FIRMSProductInfo(
        product_id="VIIRS_NOAA20_SP",
        satellite_instrument="VIIRS NOAA-20 (JPSS-1)",
        product_type="SP",
    ),
    "VIIRS_NOAA21_NRT": FIRMSProductInfo(
        product_id="VIIRS_NOAA21_NRT",
        satellite_instrument="VIIRS NOAA-21 (JPSS-2)",
        product_type="NRT",
    ),
    "VIIRS_NOAA21_SP": FIRMSProductInfo(
        product_id="VIIRS_NOAA21_SP",
        satellite_instrument="VIIRS NOAA-21 (JPSS-2)",
        product_type="SP",
    ),
}


def product_info(source: str) -> FIRMSProductInfo:
    try:
        return FIRMS_PRODUCTS[source]
    except KeyError as exc:
        raise ValueError(f"Unsupported FIRMS source: {source!r}") from exc


def redact_secrets(text: str, *secrets: str) -> str:
    """Remove credential-like substrings from user-visible messages."""
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[REDACTED]")
    return out
