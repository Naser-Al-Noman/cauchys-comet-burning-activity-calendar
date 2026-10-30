"""Download NASA FIRMS active-fire detections for planned analysis."""

from .batch import (
    ChunkResult,
    covered_dates,
    download_date_range,
    iter_chunk_starts,
    merge_csv_files,
    parse_iso_date,
)
from .firms import FIRMS_SOURCES, download_area_csv
from .manifest import (
    ACQUISITION_MANIFEST_SCHEMA,
    build_batch_acquisition_manifest,
    build_single_acquisition_manifest,
    write_acquisition_manifest,
)
from .products import FIRMS_PRODUCTS, FIRMSProductInfo, product_info
from .regions import BANGLADESH_BBOX, Region

__all__ = [
    "ACQUISITION_MANIFEST_SCHEMA",
    "BANGLADESH_BBOX",
    "ChunkResult",
    "FIRMS_PRODUCTS",
    "FIRMSProductInfo",
    "FIRMS_SOURCES",
    "Region",
    "build_batch_acquisition_manifest",
    "build_single_acquisition_manifest",
    "covered_dates",
    "download_area_csv",
    "download_date_range",
    "iter_chunk_starts",
    "merge_csv_files",
    "parse_iso_date",
    "product_info",
    "write_acquisition_manifest",
]
