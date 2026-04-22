"""Django model mixin for enrichable records.

Add EnrichableModelMixin to any model that can be enriched
from external sources. Stores enrichment data as JSONB.
"""

from __future__ import annotations

from django.db import models

from enrichment.registry import default_registry
from enrichment.types import EnrichmentResult


class EnrichableModelMixin(models.Model):
    """Abstract mixin for models that can receive external enrichment.

    Subclass must implement:
        - get_natural_key_for_enrichment() → str (e.g. CAS number)
        - get_enrichment_domain() → str (e.g. "substance")

    Usage::

        class GlobalSdsRevision(EnrichableModelMixin, models.Model):
            def get_natural_key_for_enrichment(self):
                return self.substance.cas_number or self.product_name

            def get_enrichment_domain(self):
                return "sds"
    """

    enrichment_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured enrichment data from external sources (JSONB)",
    )
    enrichment_sources = models.JSONField(
        default=list,
        blank=True,
        help_text="List of sources that contributed data",
    )
    last_enriched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last enrichment",
    )
    enrichment_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Overall confidence score (0.0–1.0)",
    )

    class Meta:
        abstract = True

    def get_natural_key_for_enrichment(self) -> str:
        """Return the natural key for enrichment lookup (e.g. CAS number)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_natural_key_for_enrichment()"
        )

    def get_enrichment_domain(self) -> str:
        """Return the enrichment domain (e.g. 'substance', 'sds', 'trade')."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_enrichment_domain()"
        )

    def apply_enrichment(self, result: EnrichmentResult) -> None:
        """Apply an EnrichmentResult to the model fields (no save).

        Call this to set enrichment fields without persisting.
        Useful for batch processing or when you need to save manually.
        """
        from django.utils import timezone

        if result.is_empty:
            return

        serialized = result.to_dict()

        existing = self.enrichment_data or {}
        existing.update(serialized)
        self.enrichment_data = existing

        sources = self.enrichment_sources or []
        for src in result.source_list:
            if src not in sources:
                sources.append(src)
        self.enrichment_sources = sources

        self.last_enriched_at = timezone.now()
        self.enrichment_confidence = result.confidence

    def run_enrichment(self, registry=None, save: bool = True) -> EnrichmentResult:
        """Execute enrichment, apply results, optionally save.

        Args:
            registry: EnrichmentRegistry to use (default: default_registry).
            save: Whether to save the model after enrichment.
                  Uses ``update_fields`` for efficiency if the instance
                  already has a primary key; falls back to full save otherwise.

        Returns:
            Merged EnrichmentResult.
        """
        reg = registry or default_registry
        domain = self.get_enrichment_domain()
        key = self.get_natural_key_for_enrichment()

        result = reg.enrich_merged(domain, key)
        self.apply_enrichment(result)

        if save and not result.is_empty:
            enrichment_fields = [
                "enrichment_data",
                "enrichment_sources",
                "last_enriched_at",
                "enrichment_confidence",
            ]
            if self.pk:
                self.save(update_fields=enrichment_fields)
            else:
                self.save()

        return result
