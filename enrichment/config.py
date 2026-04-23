"""Central configuration defaults for iil-enrichment.

Override via environment variables (``IIL_ENRICHMENT_*``) or by passing
explicit values to providers / the HTTP client factory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_cache_dir() -> Path:
    """Project-relative cache dir. Override via IIL_ENRICHMENT_CACHE_DIR."""
    override = os.environ.get("IIL_ENRICHMENT_CACHE_DIR")
    return Path(override) if override else Path.cwd() / ".cache" / "iil-enrichment"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class HTTPDefaults:
    """Tunable defaults for the HTTP layer."""

    timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("IIL_ENRICHMENT_TIMEOUT", "15"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("IIL_ENRICHMENT_MAX_RETRIES", "3"))
    )
    backoff_initial: float = field(
        default_factory=lambda: float(
            os.environ.get("IIL_ENRICHMENT_BACKOFF_INITIAL", "0.5")
        )
    )
    backoff_max: float = field(
        default_factory=lambda: float(
            os.environ.get("IIL_ENRICHMENT_BACKOFF_MAX", "8.0")
        )
    )
    cache_enabled: bool = field(
        default_factory=lambda: _env_bool("IIL_ENRICHMENT_CACHE", True)
    )
    cache_dir: Path = field(default_factory=_default_cache_dir)
    rate_limit_enabled: bool = field(
        default_factory=lambda: _env_bool("IIL_ENRICHMENT_RATE_LIMIT", True)
    )
    user_agent: str = field(
        default_factory=lambda: os.environ.get(
            "IIL_ENRICHMENT_USER_AGENT", "iil-enrichment/0.2 (+https://iil.gmbh)"
        )
    )


HTTP_DEFAULTS = HTTPDefaults()

# Per-provider cache TTL (seconds).
DEFAULT_TTLS: dict[str, int] = {
    "GESTIS": 86_400 * 7,
    "PubChem": 86_400 * 7,
}

# Per-provider rate limit (requests per second).
DEFAULT_RATE_LIMITS: dict[str, float] = {
    "GESTIS": 5.0,
    "PubChem": 5.0,
}
