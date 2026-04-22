"""iil-enrichment — Enrichment Agent Pattern (ADR-169).

Bridge managed records with external knowledge sources.
Pure Python core, optional Django integration.
"""

__version__ = "0.1.0"

from enrichment.provider import EnrichmentProvider
from enrichment.registry import EnrichmentRegistry, default_registry
from enrichment.types import CAS_PATTERN, EnrichmentResult, PropertyValue, ValueType

__all__ = [
    "CAS_PATTERN",
    "EnrichmentProvider",
    "EnrichmentRegistry",
    "EnrichmentResult",
    "PropertyValue",
    "ValueType",
    "default_registry",
]
