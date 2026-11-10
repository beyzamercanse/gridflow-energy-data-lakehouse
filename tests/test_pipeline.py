"""Local content-addressed Bronze/Silver reruns and revised-source behavior."""

import json
from datetime import date

import pyarrow.parquet as pq

from gridflow.pipeline import process_partition


def observation(value: float):
    return {
        "timezone": "Europe/Berlin",
        "unit": "EUR/MWh",
        "interval_minutes": 60,
        "data": [{"timestamp": "2024-01-01T00:00:00+01:00", "values": {"price": value}}],
    }


def test_local_reprocessing_is_idempotent_and_versioned(tmp_path):
    options = {
        "request_url": "https://api.energy-charts.info/v2/price?bzn=DE-LU",
        "source": "energy_price",
        "partition": "DE-LU",
        "day": date(2024, 1, 1),
        "local_dir": tmp_path,
    }
    a = process_partition(payload=observation(3.0), **options)
    b = process_partition(payload=observation(3.0), **options)
    c = process_partition(payload=observation(4.0), **options)
    assert a["bronze_cached"] is False
    assert b["bronze_cached"] is True
    assert a["source_sha256"] == b["source_sha256"]
    assert c["source_sha256"] != a["source_sha256"]
    assert a["silver_rows"] == 1
    assert len(list(tmp_path.rglob("*.parquet"))) == 2
    parquet_file = next(tmp_path.rglob("*.parquet"))
    result = pq.ParquetFile(parquet_file).read().to_pylist()[0]
    assert result["source_sha256"] in {a["source_sha256"], c["source_sha256"]}
    provenance_files = list(tmp_path.rglob("*.metadata.json"))
    assert len(provenance_files) == 2
    assert "sha256" in json.loads(provenance_files[0].read_text())


def test_invalid_source_is_rejected_before_writing(tmp_path):
    payload = observation(10.0)
    del payload["unit"]
    try:
        process_partition(
            payload=payload,
            request_url="https://example.invalid/",
            source="energy_price",
            partition="DE-LU",
            day=date(2024, 1, 1),
            local_dir=tmp_path,
        )
    except ValueError as exc:
        assert "unit" in str(exc)
    else:
        raise AssertionError("Expected invalid source")
    assert not list(tmp_path.rglob("*.json"))

