"""Content-addressed Bronze JSON storage with provenance sidecars."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class SavedBatch:
    content_path: Path
    metadata_path: Path
    sha256: str
    already_exists: bool


def save_bronze(
    directory: Path,
    source: str,
    day: date,
    payload: dict,
    request_url: str,
) -> SavedBatch:
    """Save source JSON once per exact response, safely rerunnable."""
    if source not in {"energy_price", "weather_hourly"}:
        raise ValueError("Unsupported source name")
    canonical = (json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    partition = directory / source / f"date={day.isoformat()}"
    path = partition / f"{digest}.json"
    metadata_path = partition / f"{digest}.metadata.json"
    cached = path.exists()

    if not cached:
        partition.mkdir(parents=True, exist_ok=True)
        # Temp-file+replace makes retries safe after interrupted writes.
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_bytes(canonical)
        temp_path.replace(path)
    if not metadata_path.exists():
        metadata = {
            "source": source,
            "partition_date": day.isoformat(),
            "sha256": digest,
            "request_url": request_url,
            "fetched_at_utc": datetime.now(UTC).isoformat(),
            "license": "CC BY 4.0 (attribution required)",
        }
        temp_metadata = metadata_path.with_suffix(".json.tmp")
        temp_metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        temp_metadata.replace(metadata_path)
    return SavedBatch(path, metadata_path, digest, cached)
