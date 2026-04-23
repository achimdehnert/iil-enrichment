# Changelog

All notable changes to `iil-enrichment` will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

## [0.2.0] — 2026-04-23

### Added
- `enrichment/config.py` — `HTTPDefaults` dataclass with env-var driven configuration (`IIL_ENRICHMENT_*`)
- `enrichment/_http.py` — central HTTP stack: `build_client()` + `get_json()` with retry (tenacity), cache (hishel), rate-limit (pyrate-limiter)
- `enrichment/providers/_base.py` — `HTTPProviderBase` with thread-safe lazy httpx.Client
- `tests/test_http.py` — 10 tests for retry, cache, rate-limit

### Changed
- **GESTISProvider** → subclass `HTTPProviderBase`, uses `get_json()`, deprecation shim for `timeout=`/`api_key=`
- **PubChemProvider** → subclass `HTTPProviderBase`, uses `get_json()`, deprecation shim for `timeout=`
- Dependencies: `requests` → `httpx` + `tenacity` + `hishel` + `pyrate-limiter` (all optional via `[http]` extra)
- Tests migrated from `MagicMock` to `respx`

### Removed
- Direct `requests` dependency

## [0.1.0] — 2026-04-22

### Added
- Initial package skeleton (ADR-169)
- `EnrichmentProvider` Protocol — domain-scoped provider contract
- `EnrichmentRegistry` — central dispatch with `enrich()` and `enrich_merged()`
- `EnrichableModelMixin` — Django model mixin for JSONB enrichment storage
- `GESTISProvider` — DGUV GESTIS API (identity, GHS, CMR, physical properties, regulations)
- `PubChemProvider` — NCBI PubChem REST API (molecular data, GHS classification)
- `ghs.py` — shared H-Statement map + `h_codes_to_descriptions()` utility
- `PropertyValue`, `EnrichmentResult`, `ValueType` core data types
- Full test suite (73 tests)
