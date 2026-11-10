"""One partition: immutable Bronze JSON plus typed Silver Parquet."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa

from gridflow.lake import ObjectLake, write_local_silver
from gridflow.silver import normalize_prices, normalize_weather
from gridflow.store import save_bronze


def table_for_source(
    payload: dict, *, source: str, partition: str, sha256: str
) -> pa.Table:
    if source == "energy_price":
        return normalize_prices(payload, bidding_zone=partition, source_sha256=sha256)
    if source == "weather_hourly":
        return normalize_weather(payload, location_id=partition, source_sha256=sha256)
    raise ValueError("Unknown source")


def process_partition(
    *,
    payload: dict,
    request_url: str,
    source: str,
    partition: str,
    day: date,
    local_dir: Path,
    lake: ObjectLake | None = None,
    normalize: bool = True,
) -> dict[str, Any]:
    """Re-runs reuse content hashes; changes create new versioned S3 keys."""
    # Validate BEFORE writing either layer, avoiding an unprocessable raw batch.
    table = (
        table_for_source(payload, source=source, partition=partition, sha256="pending")
        if normalize else None
    )
    batch = save_bronze(local_dir / "bronze", source, day, payload, request_url)
    outcome: dict[str, Any] = {
        "source_sha256": batch.sha256,
        "local_bronze": str(batch.content_path),
        "bronze_cached": batch.already_exists,
    }
    if lake:
        lake.ensure_bucket()
        raw, metadata = lake.upload_bronze(batch, source=source, day=day)
        outcome["s3_bronze_key"] = raw.key
        outcome["s3_metadata_key"] = metadata.key
        outcome["s3_bronze_created"] = raw.created
    if table is not None:
        # The exact content SHA is included in every Silver row for traceability.
        table = table_for_source(
            payload, source=source, partition=partition, sha256=batch.sha256
        )
        outcome["silver_rows"] = table.num_rows
        if lake:
            result = lake.upload_silver(
                table,
                source=source,
                partition=partition,
                day=day,
                source_sha256=batch.sha256,
            )
            outcome["s3_silver_key"] = result.key
            outcome["s3_silver_created"] = result.created
        else:
            path = write_local_silver(
                table,
                local_dir / "silver",
                source=source,
                partition=partition,
                day=day,
                source_sha256=batch.sha256,
            )
            outcome["local_silver"] = str(path)
    return outcome
