"""Central HTTP stack: cached + retried + rate-limited httpx client.

Providers should never instantiate ``httpx.Client`` themselves — they
go through :func:`build_client` so that retry, cache and rate-limit
policies are uniform.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from enrichment.config import HTTP_DEFAULTS, HTTPDefaults

logger = logging.getLogger(__name__)

# HTTP status codes worth retrying. Other 4xx are client errors and
# won't be fixed by retrying.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

_TRANSIENT_EXC = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def _is_retryable(exc: BaseException) -> bool:
    """Decide whether an exception warrants a retry."""
    if isinstance(exc, _TRANSIENT_EXC):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


def _log_before_sleep(state: RetryCallState) -> None:
    exc = state.outcome.exception() if state.outcome else None
    sleep = state.next_action.sleep if state.next_action else 0.0
    logger.warning(
        "HTTP retry attempt=%s sleep=%.2fs cause=%s",
        state.attempt_number,
        sleep,
        exc,
    )


def _make_rate_limiter(rate_per_second: float):
    """Return a no-arg callable that blocks until a token is available.

    Returns ``None`` if pyrate-limiter is not installed (graceful degradation).
    """
    try:
        from pyrate_limiter import Duration, Limiter, Rate
    except ImportError:
        logger.info("pyrate-limiter not installed — rate limiting disabled")
        return None

    rate = Rate(int(max(1, rate_per_second)), Duration.SECOND)
    limiter = Limiter(rate)

    def acquire() -> None:
        # Single global bucket per client (provider-scoped).
        # blocking=True waits until a token is available.
        limiter.try_acquire("default", blocking=True)

    return acquire


def build_client(
    *,
    defaults: HTTPDefaults | None = None,
    cache_namespace: str | None = None,
    cache_ttl: int | None = None,
    rate_limit_per_second: float | None = None,
) -> httpx.Client:
    """Build a configured ``httpx.Client``.

    Caching activates when all three are true:
        - ``cache_namespace`` provided
        - ``defaults.cache_enabled`` true
        - ``hishel`` installed

    Rate limiting activates analogously.
    """
    defaults = defaults or HTTP_DEFAULTS
    headers = {
        "Accept": "application/json",
        "User-Agent": defaults.user_agent,
    }
    timeout = httpx.Timeout(defaults.timeout_seconds)

    client: httpx.Client
    if cache_namespace and defaults.cache_enabled:
        try:
            import hishel

            cache_path = defaults.cache_dir / cache_namespace
            cache_path.mkdir(parents=True, exist_ok=True)
            db_path = cache_path / "cache.db"
            storage = hishel.SyncSqliteStorage(
                database_path=str(db_path),
                default_ttl=cache_ttl,
            )
            policy = hishel.SpecificationPolicy(
                cache_options=hishel.CacheOptions(allow_stale=True),
            )
            base_transport = httpx.HTTPTransport()
            proxy = hishel.SyncCacheProxy(
                request_sender=base_transport.handle_request,
                storage=storage,
                policy=policy,
            )
            # Wrap proxy so httpx.Client.close() works cleanly.
            proxy.close = lambda: base_transport.close()  # type: ignore[attr-defined]
            client = httpx.Client(
                transport=proxy,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
        except ImportError:
            logger.info("hishel not installed — proceeding without HTTP cache")
            client = httpx.Client(
                headers=headers, timeout=timeout, follow_redirects=True
            )
    else:
        client = httpx.Client(
            headers=headers, timeout=timeout, follow_redirects=True
        )

    # Attach rate limiter (or None) to the client instance.
    if rate_limit_per_second and defaults.rate_limit_enabled:
        client._rate_limit_acquire = _make_rate_limiter(rate_limit_per_second)  # type: ignore[attr-defined]
    else:
        client._rate_limit_acquire = None  # type: ignore[attr-defined]

    return client


def get_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    defaults: HTTPDefaults | None = None,
    expect_status: tuple[int, ...] = (200,),
) -> dict | list | None:
    """GET + JSON-decode with central retry + rate-limit policy.

    Returns ``None`` for any non-expected status code that survived retries
    (e.g. real 404 — not retryable, not an error from our perspective).

    Raises:
        httpx.HTTPError: For transport errors that exceeded retries.
        ValueError: If the response body is not valid JSON.
    """
    defaults = defaults or HTTP_DEFAULTS
    decorated = retry(
        stop=stop_after_attempt(defaults.max_retries),
        wait=wait_exponential_jitter(
            initial=defaults.backoff_initial,
            max=defaults.backoff_max,
        ),
        retry=retry_if_exception(_is_retryable),
        before_sleep=_log_before_sleep,
        reraise=True,
    )(_do_get)
    return decorated(client, url, params, expect_status)


def _do_get(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None,
    expect_status: tuple[int, ...],
) -> dict | list | None:
    # Rate-limit gate (no-op if disabled or unavailable).
    acquire = getattr(client, "_rate_limit_acquire", None)
    if acquire is not None:
        acquire()

    resp = client.get(url, params=params)
    if resp.status_code not in expect_status:
        if resp.status_code in _RETRYABLE_STATUS:
            resp.raise_for_status()  # triggers retry
        return None  # genuine miss (e.g. 404), no retry
    return resp.json()
