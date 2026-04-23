# iil-enrichment

**Enrichment Agent Pattern** — bridge managed records with external knowledge sources.

> ADR-169: Generic pattern for enriching document-centric records (SDS, GBU, tenders, trades)
> with data from authoritative external APIs (GESTIS, PubChem, ECHA, market data, etc.)

## Installation

```bash
# Core only (no providers)
pip install iil-enrichment

# With GESTIS provider
pip install iil-enrichment[gestis]

# With Django integration
pip install iil-enrichment[django]

# Everything
pip install iil-enrichment[all]
```

## Quick Start

```python
from enrichment.registry import EnrichmentRegistry
from enrichment.providers.gestis import GESTISProvider
from enrichment.providers.pubchem import PubChemProvider

# Setup registry
registry = EnrichmentRegistry()
registry.register("substance", GESTISProvider())
registry.register("substance", PubChemProvider())

# Enrich a substance by CAS number
result = registry.enrich_merged("substance", "67-64-1")

# Access structured data
print(result.get("agw"))           # AGW from GESTIS
print(result.get("first_aid"))     # First aid from GESTIS
print(result.get("molecular_formula"))  # Formula from PubChem
print(result.confidence)           # 0.0–1.0
```

## Django Integration

```python
from enrichment.django.mixins import EnrichableModelMixin

class GlobalSdsRevision(EnrichableModelMixin, models.Model):
    substance = models.ForeignKey(...)

    def get_natural_key_for_enrichment(self):
        return self.substance.cas_number or self.product_name

    def get_enrichment_domain(self):
        return "sds"

# Usage
revision.run_enrichment()  # → fetches GESTIS + PubChem, stores in enrichment_data JSONB
```

## Architecture

```
┌──────────────┐     ┌──────────────────────┐
│ Managed      │     │ EnrichmentRegistry   │
│ Record       │────▶│                      │
│ (DMS-focus)  │     │  ┌──────────────┐   │
│              │     │  │ GESTISProv.  │   │
│ enrichment_  │◀────│  │ PubChemProv. │   │
│ data (JSONB) │     │  │ CustomProv.  │   │
└──────────────┘     │  └──────────────┘   │
                     └──────────────────────┘
```

## Built-in Providers

| Provider | Domain | Data |
|----------|--------|------|
| `GESTISProvider` | substance, sds | AGW, first aid, storage, transport, WGK, physical properties |
| `PubChemProvider` | substance, sds | Molecular data, GHS classification, H/P codes |

## Configuration via Environment

All settings have sensible defaults and can be overridden per environment:

| Env-Var                          | Default                     | Description                                |
|----------------------------------|-----------------------------|--------------------------------------------|
| `IIL_ENRICHMENT_TIMEOUT`         | `15`                        | HTTP timeout in seconds                    |
| `IIL_ENRICHMENT_MAX_RETRIES`     | `3`                         | Max retry attempts per request             |
| `IIL_ENRICHMENT_BACKOFF_INITIAL` | `0.5`                       | Initial backoff in seconds                 |
| `IIL_ENRICHMENT_BACKOFF_MAX`     | `8.0`                       | Max backoff in seconds                     |
| `IIL_ENRICHMENT_CACHE`           | `1`                         | Cache on (`1`) or off (`0`)                |
| `IIL_ENRICHMENT_CACHE_DIR`       | `./.cache/iil-enrichment/`  | Cache directory                            |
| `IIL_ENRICHMENT_RATE_LIMIT`      | `1`                         | Rate limit on (`1`) or off (`0`)           |
| `IIL_ENRICHMENT_USER_AGENT`      | `iil-enrichment/0.2 ...`   | User-Agent for external APIs               |
| `GESTIS_API_KEY`                 | (public demo key)           | Own DGUV key recommended for production    |

Or configure programmatically:

```python
from enrichment.config import HTTPDefaults
from enrichment.providers.gestis import GESTISProvider

defaults = HTTPDefaults(timeout_seconds=30, max_retries=5, cache_enabled=True)
provider = GESTISProvider(defaults=defaults)
```

## Custom Provider

```python
from enrichment.provider import EnrichmentProvider
from enrichment.types import EnrichmentResult, PropertyValue

class MyProvider:
    @property
    def name(self) -> str:
        return "MySource"

    @property
    def supported_domains(self) -> list[str]:
        return ["my_domain"]

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        return domain == "my_domain" and bool(natural_key)

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        # Fetch from your API...
        return EnrichmentResult(
            source=self.name,
            confidence=0.9,
            properties={"key": PropertyValue(value="data")},
            natural_key=natural_key,
        )
```

## License

MIT
