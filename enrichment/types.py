"""Core data types for enrichment results.

All types are frozen dataclasses — immutable after creation.
No Django dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class PropertyValue:
    """Single enrichment property (typed key-value).

    Attributes:
        value: The property value (numeric, text, or boolean).
        unit: Physical unit (e.g. "°C", "mg/m³", "Vol.%").
        section: Source section identifier (e.g. SDS section "9.1").
        value_type: One of "numeric", "text", "boolean", "range", "enum".
        note: Free-text annotation (e.g. "at 20°C", "closed cup").
    """

    value: str | float | bool
    unit: str = ""
    section: str = ""
    value_type: str = "text"
    note: str = ""


@dataclass(frozen=True)
class EnrichmentResult:
    """Result from one enrichment provider.

    Attributes:
        source: Provider name (e.g. "GESTIS", "PubChem").
        confidence: Quality score 0.0–1.0.
        properties: Structured key-value data.
        raw_sections: Original text per section key (for audit trail).
        natural_key: The key used for lookup (e.g. CAS number).
        enriched_at: Timestamp of enrichment.
    """

    source: str
    confidence: float
    properties: dict[str, PropertyValue] = field(default_factory=dict)
    raw_sections: dict[str, str] = field(default_factory=dict)
    natural_key: str = ""
    enriched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        """True if no properties were extracted."""
        return len(self.properties) == 0

    def get(self, key: str, default: PropertyValue | None = None) -> PropertyValue | None:
        """Lookup a property by key."""
        return self.properties.get(key, default)

    def merge(self, other: EnrichmentResult) -> EnrichmentResult:
        """Merge another result into this one (self wins on conflict)."""
        merged_props = {**other.properties, **self.properties}
        merged_raw = {**other.raw_sections, **self.raw_sections}
        return EnrichmentResult(
            source=f"{self.source}+{other.source}",
            confidence=max(self.confidence, other.confidence),
            properties=merged_props,
            raw_sections=merged_raw,
            natural_key=self.natural_key or other.natural_key,
        )
