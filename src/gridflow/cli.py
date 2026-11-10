"""Small, reproducible command-line ingestion runner."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import httpx

from gridflow.api import energy_price, historical_weather
from gridflow.store import save_bronze


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD") from exc


def main() -> None:
    parser = argparse.ArgumentParser(prog="gridflow")
    parser.add_argument("source", choices=("energy-price", "weather"))
    parser.add_argument("--date", type=parse_date, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/bronze"))
    parser.add_argument("--bzn", default="DE-LU")
    parser.add_argument("--latitude", type=float, default=52.52)
    parser.add_argument("--longitude", type=float, default=13.41)
    args = parser.parse_args()

    try:
        with httpx.Client(headers={"User-Agent": "GridFlow/0.1 (+portfolio)"}) as client:
            if args.source == "energy-price":
                payload, url = energy_price(client, args.date, zone=args.bzn)
                source = "energy_price"
            else:
                payload, url = historical_weather(
                    client, args.date, latitude=args.latitude, longitude=args.longitude
                )
                source = "weather_hourly"
        result = save_bronze(args.out, source, args.date, payload, url)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        print(f"GridFlow ingestion failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    outcome = "cached" if result.already_exists else "saved"
    print(f"{outcome}: {result.content_path}")
    print(f"sha256: {result.sha256}")


if __name__ == "__main__":
    main()
