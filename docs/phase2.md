# GridFlow Phase 2 — S3-Compatible Lake and Silver Parquet

Phase 2 adds a local S3-compatible object store and a Bronze-to-Silver normalization pipeline. It does not yet add Dagster scheduling, DuckDB/dbt Gold models, or a public deployment.

## Quickstart

Prerequisites: Docker Compose, Python 3.11+, and Git.

```bash
python -m pip install -e '.[dev,lake]'
cp .env.example .env
docker compose up -d --wait
set -a
. ./.env
set +a

gridflow energy-price --date 2024-01-01 --bzn DE-LU --s3 --silver
gridflow weather --date 2024-01-01 --latitude 52.52 --longitude 13.41 --location-id berlin --s3 --silver
```

The S3-compatible API is on http://127.0.0.1:9000 and the development console on http://127.0.0.1:9001. The example access keys are local-only; do not expose these ports publicly or reuse the credentials elsewhere.

To stop the service without deleting stored data, run `docker compose down`. **Do not run `docker compose down -v` unless you deliberately want to delete the persistent object store volume.**

### Why SILO instead of the original MinIO Docker image?

The original open-source MinIO container image became unavailable in 2026. The Compose file pins SILO `RELEASE.2026-11-09T00-00-00Z`, a community-maintained MinIO-compatible fork with preserved S3 APIs, MINIO_* settings, and object layout. It is not affiliated with MinIO Inc. Review current release and licensing policies before commercial deployment.

## Object layout

| Layer | Example object path | Record grain |
|---|---|---|
| Local Bronze | `data/bronze/energy_price/date=2024-01-01/<sha>.json` | Original complete source response |
| S3 Bronze | `bronze/source=energy_price/date=2024-01-01/<sha>.json` | Byte-for-byte source response |
| S3 Silver | `silver/source=energy_price/partition=DE-LU/date=2024-01-01/source_sha256=<sha>/part-000.parquet` | One delivery interval per source series |
| S3 Silver | `silver/source=weather_hourly/partition=berlin/date=2024-01-01/source_sha256=<sha>/part-000.parquet` | One UTC hour per weather location |

Each Silver row includes the Bronze source SHA-256. Re-ingesting an unchanged payload returns the same keys; a changed payload gets new versioned keys. Updating normalization code alone does not rewrite already-existing Silver objects. Future orchestration will add a current-version manifest and model-version governance.

## Data-quality rules

**Electricity price:** The API v2 payload supplies its market timezone and price unit, with interval duration or a recognized resolution. The pipeline refuses timezone-naive source timestamps and missing units/intervals. Intervals are converted from offset-bearing ISO 8601 local timestamps into UTC start/end, and overlaps or duplicate series/UTC start keys are rejected. No assumption is made that all intervals last one hour, or that a local day always has 24 hours. Negative electricity prices are permitted.

**Weather:** Open-Meteo is requested explicitly in UTC. Its hourly arrays must align; temperatures/wind speeds keep their original metadata units. Duplicate observations, non-contiguous hourly timestamps, and nonzero UTC offset are rejected. Null values are kept null, not silently filled.

**Provenance:** Bronze JSON includes a metadata sidecar with source URL, fetch time, checksum, and a note to review the provider's licensing and attribution requirements. The project does not convert currency or pretend an API response is a trading-quality market dataset.

## CI and integration

```bash
ruff check .
pytest -q -m 'not integration'
docker compose up -d --wait
set -a; . ./.env; set +a
pytest -q -m integration
```

GitHub Actions executes the same offline validations and an S3-compatible Docker integration test, including a re-run of the same partition and a changed-source revision. Live API availability and external cloud hosting are **not** verified in this CI.

## Data and container licenses

Energy-Charts API: https://api.energy-charts.info/ (CC BY 4.0 unless otherwise noted).

Open-Meteo historical weather: https://open-meteo.com/en/docs/historical-weather-api (confirm usage terms for commercial use).

SILO: https://github.com/pgsty/silo — security-maintained S3/MinIO compatibility.
