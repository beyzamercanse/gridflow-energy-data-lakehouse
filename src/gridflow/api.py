"""HTTP clients for Energy-Charts v2 and Open-Meteo historical weather."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

ENERGY_PRICE_ENDPOINT = "https://api.energy-charts.info/v2/price"
WEATHER_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def request_json(
    client: httpx.Client,
    endpoint: str,
    params: dict[str, str],
    *,
    max_retries: int = 3,
    sleeper: Callable[[float], Any] = time.sleep,
) -> tuple[dict, str]:
    """Retry only transient transport, 429 and 5xx failures with bounded delay."""
    if max_retries < 0:
        raise ValueError("max_retries must be nonnegative")
    for attempt in range(max_retries + 1):
        try:
            response = client.get(endpoint, params=params, timeout=20)
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt >= max_retries:
                raise
            sleeper(min(2**attempt, 8))
            continue

        retryable = response.status_code == 429 or 500 <= response.status_code <= 599
        if retryable and attempt < max_retries:
            retry_after = response.headers.get("Retry-After", "").strip()
            delay = min(2**attempt, 8)
            if retry_after.isdecimal():
                delay = min(int(retry_after), 30)
            sleeper(delay)
            continue

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"{endpoint}: expected a JSON object")
        return payload, str(response.request.url)

    raise RuntimeError("Unreachable: request loop exhausted")


def energy_price(
    client: httpx.Client, day: date, zone: str = "DE-LU"
) -> tuple[dict, str]:
    """Fetch the day-ahead spot price in the API's self-describing v2 envelope."""
    if not zone or not all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in zone):
        raise ValueError("Bidding zone is required (letters, digits and hyphens)")
    payload, url = request_json(
        client,
        ENERGY_PRICE_ENDPOINT,
        {"bzn": zone, "start": day.isoformat(), "end": day.isoformat()},
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Energy-Charts v2 price response missing data list")
    return payload, url


def historical_weather(
    client: httpx.Client,
    day: date,
    latitude: float = 52.52,
    longitude: float = 13.41,
) -> tuple[dict, str]:
    """Fetch hourly historical temperatures and wind speeds in UTC."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Latitude or longitude outside geographic bounds")
    payload, url = request_json(
        client,
        WEATHER_ENDPOINT,
        {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "hourly": "temperature_2m,wind_speed_10m",
            "timezone": "UTC",
        },
    )
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Weather response missing hourly dictionary")
    times = hourly.get("time")
    temps = hourly.get("temperature_2m")
    winds = hourly.get("wind_speed_10m")
    if not all(isinstance(item, list) for item in (times, temps, winds)):
        raise ValueError("Weather response missing requested hourly series")
    if not (len(times) == len(temps) == len(winds)):
        raise ValueError("Weather response has mismatched hourly series lengths")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Weather UTC offset not zero; prevent DST ambiguities")
    return payload, url
