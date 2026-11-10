"""Strict, unit-preserving Bronze-to-Silver normalization for European energy data.

No price-unit conversion or DST wall-clock assumptions are made. Every price
record must carry an explicit duration from the v2 source envelope or row.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

import pyarrow as pa

PRICE_SCHEMA = pa.schema(
    [
        ("bidding_zone", pa.string()),
        ("start_utc", pa.timestamp("us", tz="UTC")),
        ("end_utc", pa.timestamp("us", tz="UTC")),
        ("interval_minutes", pa.int32()),
        ("price", pa.float64()),
        ("price_unit", pa.string()),
        ("series_id", pa.string()),
        ("market_timezone", pa.string()),
        ("source_sha256", pa.string()),
    ]
)

WEATHER_SCHEMA = pa.schema(
    [
        ("location_id", pa.string()),
        ("start_utc", pa.timestamp("us", tz="UTC")),
        ("temperature_2m", pa.float64()),
        ("wind_speed_10m", pa.float64()),
        ("temperature_unit", pa.string()),
        ("wind_speed_unit", pa.string()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("source_sha256", pa.string()),
    ]
)


def _utc_instant(value: str, *, naive_is_utc: bool = False) -> datetime:
    if not isinstance(value, str):
        raise TypeError("Timestamp must be an ISO 8601 string")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        if not naive_is_utc:
            raise ValueError("Electricity timestamps require an explicit UTC offset")
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _number(value: Any, label: str, *, allow_none: bool = False) -> float | None:
    if allow_none and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a numeric value")
    n = float(value)
    if not math.isfinite(n):
        raise ValueError(f"{label} must be finite")
    return n


def _interval_minutes(row: dict, payload: dict) -> int:
    explicit = row.get("interval_minutes", payload.get("interval_minutes"))
    if isinstance(explicit, bool):
        raise TypeError("interval_minutes must be an integer")
    if isinstance(explicit, int):
        minutes = explicit
    else:
        resolution = row.get("resolution", payload.get("resolution"))
        named = {
            "hourly": 60,
            "quarter_hourly": 15,
            "quarter-hourly": 15,
            "half_hourly": 30,
            "half-hourly": 30,
            "15min": 15,
            "30min": 30,
            "60min": 60,
            "15_minutes": 15,
            "30_minutes": 30,
            "60_minutes": 60,
        }
        if resolution not in named:
            raise ValueError("Price interval length is missing or unsupported; refuse guessing")
        minutes = named[resolution]
    if not 1 <= minutes <= 1440:
        raise ValueError("Price interval length must be 1–1440 minutes")
    return minutes


def _price_series(values: dict) -> tuple[str, float | None]:
    """Allow named 'price' or a single other stable series, preserving its identity."""
    if not isinstance(values, dict) or not values:
        raise TypeError("v2 price values must be a non-empty mapping")
    if "price" in values:
        series = "price"
    elif len(values) == 1:
        series = next(iter(values))
    else:
        raise ValueError("Multiple price series without a 'price' key; select explicitly")
    return series, _number(values[series], "price", allow_none=True)


def normalize_prices(
    payload: dict, *, bidding_zone: str, source_sha256: str
) -> pa.Table:
    """Create one row per source interval (not necessarily a 60-minute interval)."""
    market_zone = payload.get("timezone")
    price_unit = payload.get("unit")
    if not isinstance(market_zone, str) or not market_zone:
        raise ValueError("Price source timezone is missing")
    if not isinstance(price_unit, str) or not price_unit:
        raise ValueError("Price unit is missing; it must never be assumed")
    records = payload.get("data")
    if not isinstance(records, list):
        raise TypeError("Price data must be a list")

    rows: list[dict] = []
    keys: set[tuple[datetime, str]] = set()
    intervals: dict[str, list[tuple[datetime, datetime]]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("Each price observation must be a mapping")
        start = _utc_instant(record.get("timestamp"))
        minutes = _interval_minutes(record, payload)
        end = start + timedelta(minutes=minutes)
        values = record.get("values")
        series_id, price = _price_series(values)
        marker = (start, series_id)
        if marker in keys:
            raise ValueError("Duplicate UTC interval and price series")
        keys.add(marker)
        intervals.setdefault(series_id, []).append((start, end))
        rows.append(
            {
                "bidding_zone": bidding_zone,
                "start_utc": start,
                "end_utc": end,
                "interval_minutes": minutes,
                "price": price,
                "price_unit": price_unit,
                "series_id": series_id,
                "market_timezone": market_zone,
                "source_sha256": source_sha256,
            }
        )

    for series, pairs in intervals.items():
        pairs.sort()
        for (_, previous_end), (next_start, _) in pairwise(pairs):
            if next_start < previous_end:
                raise ValueError(f"Overlapping UTC intervals for series {series}")
    rows.sort(key=lambda row: (row["start_utc"], row["series_id"]))
    return pa.Table.from_pylist(rows, schema=PRICE_SCHEMA)


def normalize_weather(
    payload: dict, *, location_id: str, source_sha256: str
) -> pa.Table:
    """Normalize Open-Meteo hourly observations from a UTC-requested response."""
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Weather source must use UTC (utc_offset_seconds=0)")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise TypeError("Weather hourly data must be a mapping")
    units = payload.get("hourly_units")
    if not isinstance(units, dict):
        raise TypeError("Weather hourly unit metadata is required")
    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    wind_speeds = hourly.get("wind_speed_10m")
    if not all(isinstance(x, list) for x in (times, temperatures, wind_speeds)):
        raise TypeError("Weather hourly arrays are required")
    if len(times) != len(temperatures) or len(times) != len(wind_speeds):
        raise ValueError("Weather hourly series lengths are unequal")
    temp_unit = units.get("temperature_2m")
    wind_unit = units.get("wind_speed_10m")
    if not isinstance(temp_unit, str) or not temp_unit:
        raise ValueError("Weather temperature unit missing")
    if not isinstance(wind_unit, str) or not wind_unit:
        raise ValueError("Weather wind unit missing")
    lat = _number(payload.get("latitude"), "latitude")
    lon = _number(payload.get("longitude"), "longitude")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Weather coordinates out of bounds")
    if not location_id or not location_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Location ID must be an alphanumeric slug")

    rows = []
    observed: set[datetime] = set()
    for timestamp, temperature, wind_speed in zip(times, temperatures, wind_speeds):
        start = _utc_instant(timestamp, naive_is_utc=True)
        if start in observed:
            raise ValueError("Duplicate weather UTC hour")
        observed.add(start)
        rows.append(
            {
                "location_id": location_id,
                "start_utc": start,
                "temperature_2m": _number(temperature, "temperature", allow_none=True),
                "wind_speed_10m": _number(wind_speed, "wind speed", allow_none=True),
                "temperature_unit": temp_unit,
                "wind_speed_unit": wind_unit,
                "latitude": lat,
                "longitude": lon,
                "source_sha256": source_sha256,
            }
        )
    rows.sort(key=lambda row: row["start_utc"])
    for before, after in pairwise(rows):
        if after["start_utc"] - before["start_utc"] != timedelta(hours=1):
            raise ValueError("Non-contiguous weather hourly series; investigate missing hours")
    return pa.Table.from_pylist(rows, schema=WEATHER_SCHEMA)

