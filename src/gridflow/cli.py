"""Reproducible API -> Bronze JSON -> optional Silver Parquet and S3 pipeline."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--bzn", default="DE-LU")
    parser.add_argument("--latitude", type=float, default=52.52)
    parser.add_argument("--longitude", type=float, default=13.41)
    parser.add_argument("--location-id", default="berlin")
    parser.add_argument("--silver", action="store_true", help="Normalize source data to Parquet")
    parser.add_argument("--s3", action="store_true", help="Upload Bronze and Silver to S3/MinIO")
    args = parser.parse_args()

    try:
        with httpx.Client(headers={"User-Agent": "GridFlow/0.2 (+portfolio)"}) as client:
            if args.source == "energy-price":
                payload, url = energy_price(client, args.date, zone=args.bzn)
                source = "energy_price"
                partition = args.bzn
            else:
                payload, url = historical_weather(
                    client, args.date, latitude=args.latitude, longitude=args.longitude
                )
                source = "weather_hourly"
                partition = args.location_id

        if args.silver or args.s3:
            try:
                from gridflow.lake import LakeSettings, ObjectLake
                from gridflow.pipeline import process_partition
            except ImportError as exc:
                raise RuntimeError("Install the optional lake dependencies: pip install -e '.[lake]'") from exc

            lake = ObjectLake(LakeSettings.from_env()) if args.s3 else None
            summary = process_partition(
                payload=payload,
                request_url=url,
                source=source,
                partition=partition,
                day=args.date,
                local_dir=args.out,
                lake=lake,
                normalize=args.silver,
            )
        else:
            result = save_bronze(args.out / "bronze", source, args.date, payload, url)
            summary = {
                "source_sha256": result.sha256,
                "local_bronze": str(result.content_path),
                "bronze_cached": result.already_exists,
            }
    except (TypeError, ValueError, RuntimeError, OSError, httpx.HTTPError) as exc:
        print(f"GridFlow ingestion failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
