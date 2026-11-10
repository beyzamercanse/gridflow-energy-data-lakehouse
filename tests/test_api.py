"""No live HTTP calls: deterministic API contract fixtures."""

from datetime import date

import httpx
import pytest

from gridflow.api import energy_price, historical_weather, request_json


def client_for(responder):
    return httpx.Client(transport=httpx.MockTransport(responder))


def test_energy_price_v2_contract_and_requested_date():
    def responder(request):
        assert request.url.path == "/v2/price"
        assert request.url.params["bzn"] == "DE-LU"
        assert request.url.params["start"] == "2024-01-01"
        return httpx.Response(
            200,
            json={
                "timezone": "Europe/Berlin",
                "unit": "EUR/MWh",
                "data": [{"timestamp": "2024-01-01T00:00+01:00", "values": {"price": 11.0}}],
            },
        )

    with client_for(responder) as client:
        payload, url = energy_price(client, date(2024, 1, 1))
    assert payload["data"][0]["values"]["price"] == 11.0
    assert "bzn=DE-LU" in url


def test_retries_http_429_with_retry_after():
    calls = []
    delays = []

    def responder(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    with client_for(responder) as client:
        result, _ = request_json(
            client, "https://example.test/test", {}, max_retries=1, sleeper=delays.append
        )
    assert result == {"ok": True}
    assert delays == [2]
    assert len(calls) == 2


def test_weather_hourly_arrays_are_aligned():
    with client_for(
        lambda request: httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "hourly": {
                    "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
                    "temperature_2m": [4.0, 4.3],
                    "wind_speed_10m": [5.0, 5.1],
                },
            },
        )
    ) as client:
        payload, url = historical_weather(client, date(2024, 1, 1))
    assert len(payload["hourly"]["time"]) == 2
    assert "timezone=UTC" in url


def test_bad_weather_arrays_rejected():
    with client_for(
        lambda request: httpx.Response(
            200,
            json={
                "utc_offset_seconds": 0,
                "hourly": {
                    "time": ["2024-01-01T00:00"],
                    "temperature_2m": [1.0, 2.0],
                    "wind_speed_10m": [3.0],
                },
            },
        )
    ) as client:
        with pytest.raises(ValueError, match="mismatched"):
            historical_weather(client, date(2024, 1, 1))


def test_bad_price_envelope_rejected():
    with client_for(lambda request: httpx.Response(200, json={"not_data": []})) as client:
        with pytest.raises(ValueError, match="data list"):
            energy_price(client, date(2024, 1, 1))


def test_unauthorized_not_retried():
    attempts = []

    def responder(request):
        attempts.append(request)
        return httpx.Response(401)

    with client_for(responder) as client:
        with pytest.raises(httpx.HTTPStatusError):
            request_json(client, "https://example.test/secure", {}, max_retries=3)
    assert len(attempts) == 1
