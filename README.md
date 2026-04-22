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
