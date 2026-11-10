# GridFlow — European Energy Data Lakehouse

[![CI](https://github.com/beyzamercanse/gridflow-energy-data-lakehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/beyzamercanse/gridflow-energy-data-lakehouse/actions/workflows/ci.yml)

**Data Engineering portfolio project | Python · SQL · Dagster · Docker · Parquet · S3/MinIO · DuckDB · dbt**

GridFlow is a planned, production-style data platform for ingesting, validating, processing and analyzing European electricity-market and historical weather data. **Phases 1–2 implemented:** API ingestion, immutable Bronze JSON, S3-compatible object storage, UTC-normalized Silver Parquet, checksum provenance, and automated tests. Dagster orchestration, DuckDB/dbt Gold marts, and public deployment remain planned.

## Business problem

Electricity prices, generation and weather observations arrive through separate APIs. Their intervals, timestamps, units and update schedules vary. Data consumers need a traceable, dependable dataset for market analysis without manually combining files or correcting ingestion failures.

**Goal:** build a reproducible batch-first lakehouse with historical backfills, incremental daily updates, data quality, observable pipeline runs and a queryable market analytics layer.

## Data sources

- [Fraunhofer Energy-Charts API](https://api.energy-charts.info/) — historical European electricity prices and generation statistics, subject to endpoint and market coverage.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — historical weather variables for selected reference locations.

Initial proof of concept: Germany/Luxembourg price bidding zone (DE-LU) and Berlin historical weather. Additional market zones and reference locations will follow.

## Target architecture

```text
Energy-Charts API + Open-Meteo API
               |
         Python extractors
               |
     Dagster orchestration
               |
    MinIO / S3 raw JSON (Bronze)
               |
 PyArrow validation + Parquet (Silver)
               |
  DuckDB + dbt curated models (Gold)
               |
        SQL analytics + BI

   Quality checks, run logs and alerts
      span each pipeline stage
```

See [architecture](docs/architecture.md) and [implementation roadmap](docs/roadmap.md).

## Data products (planned)

| Model | Grain | Purpose |
|---|---|---|
| `fact_day_ahead_prices` | Bidding zone + interval start + duration | Electricity prices with explicit currency and units |
| `fact_generation` | Zone + technology + interval | Generation mix and capacity trends |
| `fact_weather_hourly` | Reference location + UTC hour | Weather drivers |
| `mart_market_daily` | Zone + local market date | Price distributions and negative-price frequency |
| `mart_weather_price` | Zone/location + aligned interval | Weather–price comparisons |
| `pipeline_runs` | One asset materialization / source partition | Freshness, failures, run duration, row counts |

## Engineering principles

1. **Preserve original evidence.** Store raw API payloads, request metadata, ingestion time, checksum and source version.
2. **Idempotent partitions.** Re-running a day or market must not duplicate business records.
3. **Correct interval semantics.** Keep UTC timestamps, original market time zone, observed interval duration and source unit; handle daylight-saving transitions.
4. **Recoverability.** Use bounded retries, rate-limit backoff, checkpointed partitions and independently rerunnable failed slices.
5. **Testability.** Mock HTTP responses in unit tests and run storage/pipeline smoke tests in CI.

## Phase 2 — Local S3-compatible lakehouse

The original MinIO Docker image was withdrawn. GridFlow uses a pinned, maintained [SILO](https://github.com/pgsty/silo) container that preserves the MinIO/S3 API and settings. The local example credentials must never be reused in production.

```bash
python -m pip install -e '.[dev,lake]'
cp .env.example .env
docker compose up -d --wait
set -a
. ./.env
set +a
gridflow energy-price --date 2024-01-01 --bzn DE-LU --s3 --silver
gridflow weather --date 2024-01-01 --location-id berlin --s3 --silver
docker compose down
```

The S3 console is available at http://127.0.0.1:9001 (localhost only). Omit `--s3` to write local Silver Parquet without an S3 service. See [Phase 2 guide](docs/phase2.md).

## Run Phase 1 locally

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest -q
gridflow energy-price --date 2024-01-01 --bzn DE-LU
gridflow weather --date 2024-01-01 --latitude 52.52 --longitude 13.41
```

Commands fetch public historical API responses and save source JSON and metadata under the gitignored `data/bronze/` directory. GitHub CI only uses mocked API responses; it does not make live network requests. See [Phase 1 guide](docs/phase1.md).

## Progress

- [x] New public GitHub repository
- [x] Project charter, architecture and development roadmap
- [x] Python package and source API clients
- [x] Docker Compose / SILO S3-compatible local lake
- [x] Bronze JSON local ingestion with SHA-256 provenance
- [x] PyArrow Silver Parquet with UTC time and unit validation
- [ ] Gold marts and analytics
- [ ] Dagster schedules, backfills and monitoring
- [x] CI + API contracts, DST, interval checks, revision handling and S3 integration tests
- [ ] Gold analytics marts and BI demonstrations

**Status: Phases 1–2 implemented; Phase 3 orchestration and Phase 4 Gold analytics planned.** This project is separate from [CommerceIQ](https://github.com/beyzamercanse/commerceiq-retail-analytics).
