"""EnrichmentProvider Protocol — the contract every provider implements.

No Django dependency. Pure Python Protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from enrichment.types import EnrichmentResult


@runtime_checkable
class EnrichmentProvider(Protocol):
    """External knowledge source that can enrich a managed record.

    Providers are stateless and domain-scoped. Each provider declares
    which domains it supports (e.g. "substance", "sds", "trade").

    Attributes:
        name: Human-readable provider name (e.g. "GESTIS").
        supported_domains: List of domain strings this provider handles.
    """

    @property
    def name(self) -> str: ...

    @property
    def supported_domains(self) -> list[str]: ...

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        """Check if this provider can enrich the given domain/key.

        Quick check — should NOT make network calls.
        """
        ...

    def enrich(self, domain: str, natural_key: str) -> EnrichmentResult:
        """Fetch enrichment data from external source.

        May make network calls. Should handle errors gracefully
        and return an empty EnrichmentResult on failure.
        """
        ...
