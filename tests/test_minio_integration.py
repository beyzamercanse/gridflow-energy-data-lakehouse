"""Docker-backed S3-compatible integration test against the pinned SILO image."""

import io
import os
from datetime import date

import pyarrow.parquet as pq
import pytest
from botocore.exceptions import EndpointConnectionError

from gridflow.lake import LakeSettings, ObjectLake
from gridflow.pipeline import process_partition

pytestmark = pytest.mark.integration


def test_bronze_and_silver_are_immutable_on_s3(tmp_path):
    if not os.environ.get("S3_ENDPOINT_URL"):
        pytest.skip("Requires local S3_ENDPOINT_URL")
    lake = ObjectLake(LakeSettings.from_env())
    try:
        lake.ensure_bucket()
    except EndpointConnectionError:
        pytest.fail("S3 test service is not ready")

    payload = {
        "timezone": "Europe/Berlin",
        "unit": "EUR/MWh",
        "interval_minutes": 15,
        "data": [
            {"timestamp": "2024-01-01T00:00+01:00", "values": {"price": -1.0}},
            {"timestamp": "2024-01-01T00:15+01:00", "values": {"price": 8.0}},
        ],
    }
    options = {
        "request_url": "https://api.energy-charts.info/v2/price",
        "source": "energy_price",
        "partition": "DE-LU",
        "day": date(2024, 1, 1),
        "local_dir": tmp_path,
        "lake": lake,
    }

    first = process_partition(payload=payload, **options)
    second = process_partition(payload=payload, **options)
    assert first["s3_bronze_created"] is True
    assert second["s3_bronze_created"] is False
    assert first["s3_silver_created"] is True
    assert second["s3_silver_created"] is False
    assert first["s3_silver_key"] == second["s3_silver_key"]

    restored = pq.read_table(io.BytesIO(lake.read_bytes(first["s3_silver_key"])))
    assert restored.num_rows == 2
    assert restored["price"].to_pylist() == [-1.0, 8.0]
    assert restored["source_sha256"][0].as_py() == first["source_sha256"]
    assert lake.read_bytes(first["s3_bronze_key"]).startswith(b"{")

    altered = {
        **payload,
        "data": [
            {"timestamp": "2024-01-01T00:00+01:00", "values": {"price": 1.0}},
            payload["data"][1],
        ],
    }
    revised = process_partition(payload=altered, **options)
    assert revised["s3_silver_key"] != first["s3_silver_key"]
    assert revised["s3_silver_created"] is True
    assert lake.read_bytes(first["s3_silver_key"])

