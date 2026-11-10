"""Bronze-to-Silver contracts: time zones, intervals, grains, and source units."""

from datetime import UTC, datetime

import pytest

from gridflow.silver import normalize_prices, normalize_weather

SHA = "a" * 64


def prices(data, *, minutes=60, unit="EUR/MWh"):
    return {
        "timezone": "Europe/Berlin",
        "unit": unit,
        "interval_minutes": minutes,
        "data": [{"timestamp": stamp, "values": {"price": val}} for stamp, val in data],
    }


def weather(times, temps, wind):
    return {
        "utc_offset_seconds": 0,
        "latitude": 52.52,
        "longitude": 13.41,
        "hourly_units": {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "wind_speed_10m": wind,
        },
    }


def test_price_dst_fall_back_distinct_utc_hours():
    # Two 02:00 local hours occur on fall-back day; UTC is unambiguous.
    payload = prices(
        [("2024-10-27T02:00:00+02:00", 12.3),
         ("2024-10-27T02:00:00+01:00", 10.5)]
    )
    rows = normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA).to_pylist()
    assert len(rows) == 2
    assert rows[0]["start_utc"] == datetime(2024, 10, 27, 0, 0, tzinfo=UTC)
    assert rows[1]["start_utc"] == datetime(2024, 10, 27, 1, 0, tzinfo=UTC)
    assert rows[0]["price_unit"] == "EUR/MWh"
    assert rows[0]["interval_minutes"] == 60
    assert rows[1]["end_utc"] == datetime(2024, 10, 27, 2, 0, tzinfo=UTC)


def test_price_quarter_hour_and_negative_price():
    payload = prices(
        [("2024-01-01T12:00+01:00", -3.25),
         ("2024-01-01T12:15+01:00", 4.0)],
        minutes=15,
    )
    rows = normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA).to_pylist()
    assert [r["interval_minutes"] for r in rows] == [15, 15]
    assert rows[0]["price"] == -3.25
    assert rows[0]["end_utc"] == rows[1]["start_utc"]


def test_price_missing_timezone_offset_rejected():
    payload = prices([("2024-01-01T00:00", 1.0)])
    with pytest.raises(ValueError, match="explicit UTC offset"):
        normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA)


def test_price_missing_resolution_rejected():
    payload = prices([("2024-01-01T00:00+01:00", 1.0)])
    del payload["interval_minutes"]
    with pytest.raises(ValueError, match="interval length"):
        normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA)


def test_price_overlapping_intervals_rejected():
    payload = prices(
        [("2024-01-01T00:00+01:00", 1.0),
         ("2024-01-01T00:30+01:00", 2.0)],
        minutes=60,
    )
    with pytest.raises(ValueError, match="Overlapping"):
        normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA)


def test_price_unit_required():
    payload = prices([("2024-01-01T00:00+01:00", 1.0)], unit="")
    with pytest.raises(ValueError, match="unit"):
        normalize_prices(payload, bidding_zone="DE-LU", source_sha256=SHA)


def test_weather_utc_and_units_preserved():
    data = weather(
        ["2024-01-01T00:00", "2024-01-01T01:00"],
        [2.5, None],
        [12.0, 15.5],
    )
    rows = normalize_weather(data, location_id="berlin", source_sha256=SHA).to_pylist()
    assert len(rows) == 2
    assert rows[0]["start_utc"] == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert rows[0]["temperature_2m"] == 2.5
    assert rows[1]["temperature_2m"] is None
    assert rows[0]["wind_speed_unit"] == "km/h"


def test_weather_missing_hour_fails():
    data = weather(
        ["2024-01-01T00:00", "2024-01-01T02:00"],
        [1.0, 2.0], [3.0, 4.0]
    )
    with pytest.raises(ValueError, match="Non-contiguous"):
        normalize_weather(data, location_id="berlin", source_sha256=SHA)


def test_weather_duplicate_hour_fails():
    data = weather(
        ["2024-01-01T00:00", "2024-01-01T00:00"],
        [1.0, 2.0], [3.0, 4.0]
    )
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_weather(data, location_id="berlin", source_sha256=SHA)


def test_weather_offset_required_utc():
    data = weather(["2024-01-01T00:00"], [1.0], [3.0])
    data["utc_offset_seconds"] = 3600
    with pytest.raises(ValueError, match="UTC"):
        normalize_weather(data, location_id="berlin", source_sha256=SHA)


def test_weather_hourly_units_required():
    data = weather(["2024-01-01T00:00"], [1.0], [3.0])
    del data["hourly_units"]
    with pytest.raises(TypeError, match="unit metadata"):
        normalize_weather(data, location_id="berlin", source_sha256=SHA)

