"""Base class for HTTP-backed enrichment providers.

Centralises:
- httpx client lifecycle (thread-safe lazy init)
- can_enrich default behaviour (CAS or substance name)
- close() / context-manager support
- per-provider cache TTL and rate limit
"""

from __future__ import annotations

import threading

import httpx

from enrichment._http import build_client
from enrichment.config import (
    DEFAULT_RATE_LIMITS,
    DEFAULT_TTLS,
    HTTP_DEFAULTS,
    HTTPDefaults,
)
from enrichment.types import CAS_PATTERN


class HTTPProviderBase:
    """Mixin providing a cached, retried, rate-limited httpx.Client.

    Subclasses MUST override ``name`` and ``supported_domains`` as
    ``@property`` (to satisfy the ``EnrichmentProvider`` Protocol),
    and implement ``enrich``.
    """

    # Subclass overrides — kept as plain attributes for fallback.
    cache_ttl_seconds: int | None = None
    rate_limit_per_second: float | None = None

    def __init__(self, *, defaults: HTTPDefaults | None = None) -> None:
        self._defaults = defaults or HTTP_DEFAULTS
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def supported_domains(self) -> list[str]:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(timeout={self._defaults.timeout_seconds})"

    # -- HTTP client ------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        """Thread-safe lazy client init (double-checked locking)."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    provider_name = self.name
                    ttl = self.cache_ttl_seconds or DEFAULT_TTLS.get(provider_name)
                    rate = self.rate_limit_per_second or DEFAULT_RATE_LIMITS.get(
                        provider_name
                    )
                    self._client = build_client(
                        defaults=self._defaults,
                        cache_namespace=(
                            provider_name.lower() if provider_name else None
                        ),
                        cache_ttl=ttl,
                        rate_limit_per_second=rate,
                    )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # -- can_enrich default ----------------------------------------------

    def can_enrich(self, domain: str, natural_key: str) -> bool:
        if domain not in self.supported_domains:
            return False
        key = natural_key.strip()
        return bool(key) and (bool(CAS_PATTERN.match(key)) or len(key) >= 3)
