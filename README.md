# GridFlow — European Energy Data Lakehouse

**Data Engineering portfolio project | Python · SQL · Dagster · Docker · Parquet · S3/MinIO · DuckDB · dbt**

GridFlow is a planned, production-style data platform for ingesting, validating, processing and analyzing European electricity-market and historical weather data. **Phase 1 is implemented:** typed Python API ingestion for Energy-Charts v2 and Open-Meteo historical weather, immutable content-addressed Bronze JSON, source provenance, retry handling, offline tests, and CI. MinIO, Parquet, Dagster, DuckDB, dbt and hosting remain planned.

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
- [ ] Docker Compose / MinIO local lake
- [x] Bronze JSON local ingestion with SHA-256 provenance
- [ ] Silver Parquet and Gold models
- [ ] Dagster schedules, backfills and monitoring
- [x] CI + source contract and idempotency tests
- [ ] Gold analytics marts and BI demonstrations

**Status: Phase 1 implemented; later phases planned.** This project is separate from [CommerceIQ](https://github.com/beyzamercanse/commerceiq-retail-analytics).
