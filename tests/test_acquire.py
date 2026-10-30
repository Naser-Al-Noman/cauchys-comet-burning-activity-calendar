from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

from src.acquire.batch import (
    ChunkResult,
    covered_dates,
    download_date_range,
    iter_chunk_starts,
    merge_csv_files,
)
from src.acquire.firms import (
    FIRMSDownloadError,
    build_area_url,
    build_redacted_request_label,
    count_csv_data_rows,
    download_area_csv,
    validate_firms_csv_content,
)
from src.acquire.manifest import (
    build_batch_acquisition_manifest,
    build_single_acquisition_manifest,
    write_acquisition_manifest,
)
from src.acquire.products import FIRMS_PRODUCTS, product_info, redact_secrets

VALID_HEADER = "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,confidence\n"
VALID_ROW = "23.8,90.4,330,0.4,0.4,2024-03-04,0130,N,n\n"


def _response(text: str, status: int = 200) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = text.encode("utf-8")
    return resp


class TestFirmsDownload:
    def test_successful_csv_download(self) -> None:
        calls: list[str] = []

        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            calls.append(url)
            return _response(VALID_HEADER + VALID_ROW)

        text = download_area_csv(
            map_key="secret-key-123",
            source="VIIRS_SNPP_SP",
            area_coordinates="88,20.5,92.7,26.7",
            day_range=1,
            date="2024-03-04",
            http_get=http_get,
        )
        assert "latitude" in text
        assert count_csv_data_rows(text) == 1
        assert "secret-key-123" not in calls[0] or calls[0].count("secret-key-123") == 1
        # URL contains key by API design; errors must not echo it.

    def test_http_permanent_error_not_retried(self) -> None:
        attempts = 0

        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            nonlocal attempts
            attempts += 1
            return _response("forbidden", status=403)

        with pytest.raises(FIRMSDownloadError, match="403"):
            download_area_csv(
                map_key="k",
                source="MODIS_SP",
                area_coordinates="1,2,3,4",
                http_get=http_get,
                max_retries=3,
            )
        assert attempts == 1

    def test_http_200_api_error_message(self) -> None:
        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            return _response("Invalid MAP_KEY provided")

        with pytest.raises(FIRMSDownloadError, match="error message"):
            download_area_csv(
                map_key="super-secret",
                source="MODIS_SP",
                area_coordinates="1,2,3,4",
                http_get=http_get,
            )

    def test_timeout_retries_then_fail(self) -> None:
        attempts = 0

        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            nonlocal attempts
            attempts += 1
            raise requests.Timeout("timed out")

        with pytest.raises(FIRMSDownloadError, match="failed after"):
            download_area_csv(
                map_key="k",
                source="VIIRS_SNPP_NRT",
                area_coordinates="1,2,3,4",
                http_get=http_get,
                max_retries=2,
                backoff_seconds=0,
            )
        assert attempts == 3

    def test_retry_on_503(self) -> None:
        attempts = 0

        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return _response("busy", status=503)
            return _response(VALID_HEADER + VALID_ROW)

        text = download_area_csv(
            map_key="k",
            source="VIIRS_NOAA20_SP",
            area_coordinates="1,2,3,4",
            http_get=http_get,
            max_retries=3,
            backoff_seconds=0,
        )
        assert count_csv_data_rows(text) == 1
        assert attempts == 3

    def test_empty_csv_body(self) -> None:
        validated = validate_firms_csv_content("", map_key="k")
        assert validated.empty_dataset is True
        assert validated.data_row_count == 0

    def test_header_only_empty_dataset(self) -> None:
        validated = validate_firms_csv_content(VALID_HEADER, map_key="k")
        assert validated.header_present is True
        assert validated.data_row_count == 0
        assert validated.empty_dataset is True

    def test_invalid_csv_response(self) -> None:
        with pytest.raises(FIRMSDownloadError, match="CSV header"):
            validate_firms_csv_content("not,a,valid,response", map_key="k")

    def test_map_key_redaction_in_error_snippet(self) -> None:
        with pytest.raises(FIRMSDownloadError) as exc:
            validate_firms_csv_content(
                "Invalid key: my-map-key-value-0123456789ab",
                map_key="my-map-key-value-0123456789ab",
            )
        assert "my-map-key-value-0123456789ab" not in str(exc.value)
        assert "[REDACTED]" in str(exc.value)

    def test_redact_secrets_helper(self) -> None:
        assert redact_secrets("key=abc", "abc") == "key=[REDACTED]"

    def test_redacted_request_label_has_no_key(self) -> None:
        label = build_redacted_request_label("MODIS_SP", "88,20.5,92.7,26.7", 1, "2024-03-04")
        assert "MAP_KEY" not in label
        assert "MODIS_SP" in label


class TestChunkBoundaries:
    def test_iter_chunks_cover_inclusive_range_without_gaps_or_overlap(self) -> None:
        start = date(2024, 3, 1)
        end = date(2024, 3, 13)
        days = covered_dates(start, end, chunk_days=5)
        expected = [start + timedelta(days=i) for i in range(13)]
        assert days == expected
        assert len(set(days)) == len(days)

    def test_chunk_windows_are_contiguous(self) -> None:
        start = date(2024, 3, 1)
        end = date(2024, 3, 12)
        windows = list(iter_chunk_starts(start, end, 5))
        cursor = start
        for chunk_start, day_range in windows:
            assert chunk_start == cursor
            cursor = chunk_start + timedelta(days=day_range)


class TestBatchAndManifest:
    def test_partial_chunk_failure_records_failed_and_merges_successful(
        self, tmp_path: Path
    ) -> None:
        call = {"n": 0}

        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            call["n"] += 1
            if call["n"] == 2:
                return _response("Invalid request", status=200)
            return _response(VALID_HEADER + VALID_ROW)

        results, merged, manifest = download_date_range(
            map_key="hidden-map-key-0123456789abcdef",
            source="VIIRS_SNPP_SP",
            area_coordinates="88,20.5,92.7,26.7",
            start=date(2024, 3, 1),
            end=date(2024, 3, 6),
            out_dir=tmp_path,
            chunk_days=2,
            sleep_seconds=0,
            skip_existing=False,
            bbox={"name": "bangladesh", "west": 88.0, "south": 20.5, "east": 92.7, "north": 26.7},
            write_manifest=True,
            http_get=http_get,
        )
        assert any(r.status == "failed" for r in results)
        assert any(r.status == "success" for r in results)
        assert manifest["download_status"] == "partial_failure"
        assert len(manifest["failed_chunks"]) >= 1
        assert merged is not None
        assert "hidden-map-key-0123456789abcdef" not in json.dumps(manifest)

    def test_manifest_sha256_matches_raw_file(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.csv"
        raw.write_text(VALID_HEADER + VALID_ROW, encoding="utf-8")
        digest = hashlib.sha256(raw.read_bytes()).hexdigest()
        manifest = build_single_acquisition_manifest(
            source="VIIRS_SNPP_SP",
            area_name="bangladesh",
            bbox={"name": "bangladesh", "west": 88, "south": 20.5, "east": 92.7, "north": 26.7},
            requested_range={"start": "2024-03-04", "end": "2024-03-04", "day_range": 1},
            retrieval_timestamp="2026-01-01T00:00:00+00:00",
            raw_path=raw,
            row_count=1,
            status="success",
        )
        assert manifest["raw_file"]["sha256"] == digest

    def test_merge_preserves_raw_chunk_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        a.write_text(VALID_HEADER + VALID_ROW, encoding="utf-8")
        b.write_text(VALID_HEADER + VALID_ROW, encoding="utf-8")
        before_a = a.read_text(encoding="utf-8")
        merged = tmp_path / "merged.csv"
        merge_csv_files([a, b], merged, overwrite=True)
        assert a.read_text(encoding="utf-8") == before_a
        assert count_csv_data_rows(merged.read_text(encoding="utf-8")) == 2

    @pytest.mark.parametrize("source", list(FIRMS_PRODUCTS.keys()))
    def test_all_supported_product_identifiers(self, source: str) -> None:
        info = product_info(source)
        assert info.product_id == source
        assert info.product_type in ("NRT", "SP")

    def test_batch_manifest_written(self, tmp_path: Path) -> None:
        def http_get(url: str, timeout: float | None = None) -> requests.Response:
            return _response(VALID_HEADER + VALID_ROW)

        _, _, manifest = download_date_range(
            map_key="k",
            source="MODIS_SP",
            area_coordinates="88,20.5,92.7,26.7",
            start=date(2024, 3, 1),
            end=date(2024, 3, 1),
            out_dir=tmp_path,
            sleep_seconds=0,
            skip_existing=False,
            write_manifest=True,
            http_get=http_get,
        )
        manifest_path = Path(manifest["manifest_path"])
        assert manifest_path.is_file()
        assert manifest["product"]["product_id"] == "MODIS_SP"

