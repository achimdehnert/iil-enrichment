"""Core data types for enrichment results.

All types are frozen dataclasses — immutable after creation.
No Django dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

CAS_PATTERN = re.compile(r"^\d{1,7}-\d{2}-\d$")

# JSON-safe value types for PropertyValue.value
PropertyValueType = str | float | int | bool | list[str]


class ValueType(StrEnum):
    """Allowed value_type discriminators for PropertyValue."""

    NUMERIC = "numeric"
    TEXT = "text"
    BOOLEAN = "boolean"
    RANGE = "range"
    ENUM = "enum"
    LIST = "list"


@dataclass(frozen=True)
class PropertyValue:
    """Single enrichment property (typed key-value).

    Attributes:
        value: The property value (numeric, text, boolean, or list of strings).
        unit: Physical unit (e.g. "°C", "mg/m³", "Vol.%").
        section: Source section identifier (e.g. SDS section "9.1").
        value_type: Discriminator — see ``ValueType`` enum.
        note: Free-text annotation (e.g. "at 20°C", "closed cup").
    """

    value: PropertyValueType
    unit: str = ""
    section: str = ""
    value_type: str = ValueType.TEXT
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict (for JSONB storage)."""
        return {
            "value": self.value,
            "unit": self.unit,
            "section": self.section,
            "value_type": self.value_type,
            "note": self.note,
        }


@dataclass(frozen=True)
class EnrichmentResult:
    """Result from one enrichment provider.

    Attributes:
        source: Provider name (e.g. "GESTIS", "PubChem"), comma-separated after merge.
        confidence: Quality score 0.0–1.0.
        properties: Structured key-value data.
        raw_sections: Original text per section key (for audit trail).
        natural_key: The key used for lookup (e.g. CAS number).
        enriched_at: Timestamp of enrichment (UTC).
    """

    source: str
    confidence: float
    properties: dict[str, PropertyValue] = field(default_factory=dict)
    raw_sections: dict[str, str] = field(default_factory=dict)
    natural_key: str = ""
    enriched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_empty(self) -> bool:
        """True if no properties were extracted."""
        return len(self.properties) == 0

    @property
    def source_list(self) -> list[str]:
        """Provider names as list."""
        return self.source.split(",") if self.source else []

    def get(self, key: str, default: PropertyValue | None = None) -> PropertyValue | None:
        """Lookup a property by key."""
        return self.properties.get(key, default)

    def merge(self, other: EnrichmentResult) -> EnrichmentResult:
        """Merge another result into this one (self wins on conflict)."""
        merged_props = {**other.properties, **self.properties}
        merged_raw = {**other.raw_sections, **self.raw_sections}
        return EnrichmentResult(
            source=",".join(sorted({*self.source.split(","), *other.source.split(",")})),
            confidence=max(self.confidence, other.confidence),
            properties=merged_props,
            raw_sections=merged_raw,
            natural_key=self.natural_key or other.natural_key,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize all properties to JSON-safe dict."""
        return {key: pv.to_dict() for key, pv in self.properties.items()}
