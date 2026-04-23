"""iil-enrichment — Enrichment Agent Pattern (ADR-169).

Bridge managed records with external knowledge sources.
Pure Python core, optional Django integration.
"""

__version__ = "0.1.0"

from enrichment.ghs import H_STATEMENTS_DE, h_codes_to_descriptions
from enrichment.provider import EnrichmentProvider
from enrichment.registry import EnrichmentRegistry, default_registry
from enrichment.types import CAS_PATTERN, EnrichmentResult, PropertyValue, ValueType

__all__ = [
    "CAS_PATTERN",
    "EnrichmentProvider",
    "EnrichmentRegistry",
    "EnrichmentResult",
    "H_STATEMENTS_DE",
    "PropertyValue",
    "ValueType",
    "default_registry",
    "h_codes_to_descriptions",
]
