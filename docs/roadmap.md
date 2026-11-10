# Implementation Roadmap

Phase 1 is implemented, with offline fixture-based CI. Each milestone will be developed, tested and merged separately.

## Milestone 0 — Repository foundation (complete)

- [x] GitHub repository
- [x] Project definition and technical architecture
- [x] Staged implementation roadmap

## Milestone 1 — API ingestion (code complete)

- [x] Python package, dependencies, Ruff and pytest
- [x] Energy-Charts v2 price API client (dates, zone, timeout, 429 and 5xx retries)
- [x] Open-Meteo historical-weather API client
- [x] Validate response structures, store raw JSON and source metadata
- [x] Tests for malformed responses, HTTP errors and idempotent storage
- [x] GitHub Actions CI

**Acceptance:** offline tests and CI pass. Live external API availability remains dependent on the providers.

## Milestone 2 — Local data lake (implemented and CI-validated)

- [x] Docker Compose with maintained SILO (MinIO/S3 compatible)
- [x] Bronze JSON upload with checksum and request metadata
- [x] Silver Parquet normalization via PyArrow
- [x] UTC/DST and interval/unit validation
- [x] Idempotency and source revision integration tests

**Acceptance:** repeating a partition produces deterministic Silver results without duplicated intervals.

## Milestone 3 — Orchestration and recovery

- [ ] Dagster assets and dependency graph
- [ ] Date/market partitioning and historical backfills
- [ ] Retries, partition-level recovery and ingestion logs
- [ ] Quality checks for missing and overlapping intervals

**Acceptance:** a deliberately broken date/market partition is visible and can be rerun without reprocessing unaffected partitions.

## Milestone 4 — Analytics and demonstration

- [ ] DuckDB + dbt Gold transformations
- [ ] Price and generation marts, then weather joins
- [ ] Data dictionary and metric definitions
- [ ] BI dashboard and runnable demo
- [ ] Optional AWS S3 deployment

**Acceptance:** fresh checkout instructions work; tests pass in GitHub Actions; demonstration reproduces a historical backfill and daily update.

## Portfolio outcome

Show the complete evidence trail from external API response to a validated market analytics model, including one handled failure and one safe reprocessing run.
