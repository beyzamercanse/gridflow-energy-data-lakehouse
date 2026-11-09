# GridFlow — European Energy Data Lakehouse

**Data Engineering portfolio project | Python · SQL · Dagster · Docker · Parquet · S3/MinIO · DuckDB · dbt**

GridFlow is a planned, production-style data platform for ingesting, validating, processing and analyzing European electricity-market and historical weather data. This repository currently contains the **project charter and technical design**. No ingestion pipelines or deployed infrastructure have been implemented yet.

## Business problem

Electricity prices, generation and weather observations arrive through separate APIs. Their intervals, timestamps, units and update schedules vary. Data consumers need a traceable, dependable dataset for market analysis without manually combining files or correcting ingestion failures.

**Goal:** build a reproducible batch-first lakehouse with historical backfills, incremental daily updates, data quality, observable pipeline runs and a queryable market analytics layer.

## Data sources

- [Fraunhofer Energy-Charts API](https://api.energy-charts.info/) — historical European electricity prices and generation statistics, subject to endpoint and market coverage.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) — historical weather variables for selected reference locations.

Initial proof of concept: Netherlands and Germany/Luxembourg markets where source data is available, with selected weather stations. API access, response structure, licensing and source coverage must be verified during implementation.

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

## Progress

- [x] New public GitHub repository
- [x] Project charter, architecture and development roadmap
- [ ] Python package and source API clients
- [ ] Docker Compose / MinIO local lake
- [ ] Bronze/Silver/Gold pipelines
- [ ] Dagster schedules, backfills and monitoring
- [ ] CI/CD, data-quality tests and BI demonstrations

**Status: design stage.** This project is intentionally separate from [CommerceIQ](https://github.com/beyzamercanse/commerceiq-retail-analytics). GridFlow implementation will begin after CommerceIQ's next milestone.
