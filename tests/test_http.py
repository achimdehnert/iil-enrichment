"""Tests for the central HTTP stack: retry, cache, rate-limit."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from enrichment._http import build_client, get_json
from enrichment.config import HTTPDefaults


@pytest.fixture()
def fast_defaults(tmp_path):
    """Defaults with tiny backoff so tests run quickly."""
    return HTTPDefaults(
        timeout_seconds=2,
        max_retries=3,
        backoff_initial=0.01,
        backoff_max=0.05,
        cache_enabled=False,
        cache_dir=tmp_path,
        rate_limit_enabled=False,
    )


class TestRetry:
    @respx.mock
    def test_should_retry_on_503_then_succeed(self, fast_defaults):
        route = respx.get("https://api.test/x").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        with build_client(defaults=fast_defaults) as client:
            data = get_json(client, "https://api.test/x", defaults=fast_defaults)

        assert data == {"ok": True}
        assert route.call_count == 3

    @respx.mock
    def test_should_not_retry_on_404(self, fast_defaults):
        route = respx.get("https://api.test/x").mock(
            return_value=httpx.Response(404)
        )
        with build_client(defaults=fast_defaults) as client:
            data = get_json(client, "https://api.test/x", defaults=fast_defaults)

        assert data is None
        assert route.call_count == 1

    @respx.mock
    def test_should_retry_on_timeout(self, fast_defaults):
        route = respx.get("https://api.test/x").mock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        with build_client(defaults=fast_defaults) as client:
            data = get_json(client, "https://api.test/x", defaults=fast_defaults)

        assert data == {"ok": True}
        assert route.call_count == 2

    @respx.mock
    def test_should_give_up_after_max_retries(self, fast_defaults):
        respx.get("https://api.test/x").mock(
            return_value=httpx.Response(503)
        )
        with build_client(defaults=fast_defaults) as client, pytest.raises(httpx.HTTPStatusError):
            get_json(client, "https://api.test/x", defaults=fast_defaults)

    @respx.mock
    def test_should_retry_on_429(self, fast_defaults):
        route = respx.get("https://api.test/x").mock(
            side_effect=[
                httpx.Response(429),
                httpx.Response(200, json={"ok": True}),
            ]
        )
        with build_client(defaults=fast_defaults) as client:
            data = get_json(client, "https://api.test/x", defaults=fast_defaults)

        assert data == {"ok": True}
        assert route.call_count == 2

    @respx.mock
    def test_should_not_retry_on_400(self, fast_defaults):
        route = respx.get("https://api.test/x").mock(
            return_value=httpx.Response(400)
        )
        with build_client(defaults=fast_defaults) as client:
            data = get_json(client, "https://api.test/x", defaults=fast_defaults)

        assert data is None
        assert route.call_count == 1


class TestCache:
    def test_should_create_cached_client(self, tmp_path):
        """Verify that build_client configures cache transport when enabled."""
        defaults = HTTPDefaults(
            timeout_seconds=2,
            max_retries=1,
            cache_enabled=True,
            cache_dir=tmp_path,
            rate_limit_enabled=False,
        )
        client = build_client(
            defaults=defaults, cache_namespace="test", cache_ttl=3600
        )
        # The client should use hishel's SyncCacheProxy as transport.
        transport = client._transport
        assert type(transport).__name__ == "SyncCacheProxy"
        # Cache DB should be created in the expected path.
        assert (tmp_path / "test" / "cache.db").parent.exists()
        client.close()

    def test_should_skip_cache_when_disabled(self, fast_defaults):
        client = build_client(
            defaults=fast_defaults, cache_namespace="test", cache_ttl=3600
        )
        assert type(client._transport).__name__ != "SyncCacheProxy"
        client.close()


class TestRateLimit:
    @respx.mock
    def test_should_throttle_to_configured_rate(self, tmp_path):
        defaults = HTTPDefaults(
            timeout_seconds=2,
            max_retries=1,
            cache_enabled=False,
            cache_dir=tmp_path,
            rate_limit_enabled=True,
        )
        respx.get("https://api.test/x").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        # 2 req/s → 3 calls take at least ~1s
        with build_client(defaults=defaults, rate_limit_per_second=2.0) as client:
            start = time.monotonic()
            for _ in range(3):
                get_json(client, "https://api.test/x", defaults=defaults)
            elapsed = time.monotonic() - start

        assert elapsed >= 0.9  # allow a little slack on slow CI


class TestBuildClient:
    def test_should_create_plain_client_without_cache(self, fast_defaults):
        client = build_client(defaults=fast_defaults)
        assert isinstance(client, httpx.Client)
        client.close()

    def test_should_attach_rate_limiter_when_enabled(self, tmp_path):
        defaults = HTTPDefaults(
            timeout_seconds=2,
            max_retries=1,
            cache_enabled=False,
            cache_dir=tmp_path,
            rate_limit_enabled=True,
        )
        client = build_client(defaults=defaults, rate_limit_per_second=5.0)
        assert client._rate_limit_acquire is not None  # type: ignore[attr-defined]
        client.close()

    def test_should_not_attach_rate_limiter_when_disabled(self, fast_defaults):
        client = build_client(defaults=fast_defaults, rate_limit_per_second=5.0)
        assert client._rate_limit_acquire is None  # type: ignore[attr-defined]
        client.close()
