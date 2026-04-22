"""EnrichmentRegistry — central dispatch for enrichment providers.

No Django dependency. Pure Python.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from enrichment.provider import EnrichmentProvider
from enrichment.types import EnrichmentResult

logger = logging.getLogger(__name__)


class EnrichmentRegistry:
    """Central registry of enrichment providers per domain.

    Usage::

        registry = EnrichmentRegistry()
        registry.register("substance", GESTISProvider())
        registry.register("substance", PubChemProvider())

        results = registry.enrich("substance", "67-64-1")
        # → [EnrichmentResult(source="GESTIS", ...), EnrichmentResult(source="PubChem", ...)]

        merged = registry.enrich_merged("substance", "67-64-1")
        # → single EnrichmentResult with all properties merged
    """

    def __init__(self) -> None:
        self._providers: dict[str, list[EnrichmentProvider]] = defaultdict(list)

    def register(self, domain: str, provider: EnrichmentProvider) -> None:
        """Register a provider for a domain."""
        if provider in self._providers[domain]:
            logger.warning("Provider %s already registered for domain %s", provider.name, domain)
            return
        self._providers[domain].append(provider)
        logger.info("Registered provider %s for domain %s", provider.name, domain)

    def unregister(self, domain: str, provider_name: str) -> bool:
        """Remove a provider by name. Returns True if found."""
        before = len(self._providers[domain])
        self._providers[domain] = [
            p for p in self._providers[domain] if p.name != provider_name
        ]
        return len(self._providers[domain]) < before

    def get_providers(self, domain: str) -> list[EnrichmentProvider]:
        """List all providers for a domain."""
        return list(self._providers[domain])

    @property
    def domains(self) -> list[str]:
        """List all registered domains."""
        return [d for d, providers in self._providers.items() if providers]

    def enrich(self, domain: str, natural_key: str) -> list[EnrichmentResult]:
        """Run all providers for domain, return individual results.

        Errors in individual providers are logged but don't stop others.
        """
        results: list[EnrichmentResult] = []
        for provider in self._providers.get(domain, []):
            if not provider.can_enrich(domain, natural_key):
                logger.debug(
                    "Provider %s cannot enrich domain=%s key=%s",
                    provider.name,
                    domain,
                    natural_key,
                )
                continue
            try:
                result = provider.enrich(domain, natural_key)
                if not result.is_empty:
                    results.append(result)
                    logger.info(
                        "Provider %s enriched domain=%s key=%s (%d properties)",
                        provider.name,
                        domain,
                        natural_key,
                        len(result.properties),
                    )
            except Exception:
                logger.exception(
                    "Provider %s failed for domain=%s key=%s",
                    provider.name,
                    domain,
                    natural_key,
                )
        return results

    def enrich_merged(self, domain: str, natural_key: str) -> EnrichmentResult:
        """Run all providers and merge results.

        First provider's results are base, subsequent providers fill gaps.
        Returns empty result if no providers succeed.
        """
        results = self.enrich(domain, natural_key)
        if not results:
            return EnrichmentResult(
                source="none",
                confidence=0.0,
                natural_key=natural_key,
            )

        merged = results[0]
        for result in results[1:]:
            merged = merged.merge(result)
        return merged


# Singleton registry — import and use directly
default_registry = EnrichmentRegistry()
