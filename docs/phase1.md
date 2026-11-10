# GridFlow Phase 1 — API ingestion (implemented)

**Purpose:** demonstrate defensible batch ingestion from two published energy-market and weather APIs, with bounded retries, source schema validation, content hashes, provenance and offline CI tests.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
pytest -q
```

## Run a historical slice

```bash
gridflow energy-price --date 2024-01-01 --bzn DE-LU
gridflow weather --date 2024-01-01 --latitude 52.52 --longitude 13.41
```

Each command stores the complete returned JSON in `data/bronze/<source>/date=YYYY-MM-DD/<sha256>.json` plus metadata with request URL, UTC fetch time, source, license and SHA-256 digest.

The default data directory is gitignored, and the official APIs are **not** called by CI. The price client uses the Energy-Charts **v2** self-describing API (released July 2026) rather than its older v1 response. It keeps the complete original response because interval metadata may vary by source/bidding zone.

Open-Meteo weather is requested in UTC to eliminate ambiguous daylight-saving wall-clock timestamps in source responses. Price intervals retain their provided local timezone and explicit metadata; canonical UTC normalization is planned for Phase 2.

## Limits and next steps

This is a robust **Bronze layer**, not yet a production lakehouse. Phase 2 will add MinIO/S3, PyArrow Silver Parquet normalization, time interval validation, and database/catalog metadata. Later phases will include Dagster partitions/backfills, DuckDB/dbt, marts and BI.

Never claim prices have unit EUR/MWh unless response metadata confirms it. Both Energy-Charts and Open-Meteo require source attribution and have usage terms; verify commercial permissions before republishing data.

[Energy-Charts API](https://api.energy-charts.info/) | [Open-Meteo Historical API](https://open-meteo.com/en/docs/historical-weather-api)
