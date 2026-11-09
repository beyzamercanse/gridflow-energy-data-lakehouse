# Implementation Roadmap

The repository begins with design and documentation only. Each milestone will be developed, tested and merged separately.

## Milestone 0 — Repository foundation (complete)

- [x] GitHub repository
- [x] Project definition and technical architecture
- [x] Staged implementation roadmap

## Milestone 1 — API ingestion

- [ ] Set up Python package, pinned dependencies, Ruff and pytest
- [ ] Implement Energy-Charts API client (dates, zone, timeout, rate limiting)
- [ ] Implement Open-Meteo historical-weather client
- [ ] Validate API responses and preserve source metadata
- [ ] Build fixture-driven tests for malformed responses and API errors
- [ ] Add CI

**Acceptance:** CLI can fetch a small historical range, outputs well-formed raw responses, and passes tests with mocked APIs.

## Milestone 2 — Local data lake

- [ ] Docker Compose and MinIO
- [ ] Bronze JSON upload with checksum and request metadata
- [ ] Silver normalization to Parquet using PyArrow
- [ ] UTC and DST tests, interval and currency/unit validation
- [ ] Idempotency and revision-handling integration tests

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
