"""Outbound HTTP transport with host allow-list enforcement.

SC-7.4: the proxy must never open connections to hosts outside the configured
``providers.*.upstream`` set. This wraps ``httpx.AsyncHTTPTransport`` and
refuses to dispatch requests to any other host at the transport layer, before
DNS resolution.
"""

from __future__ import annotations

from collections.abc import Iterable

import httpx


class BlockedHostError(RuntimeError):
    """Raised when an outbound request targets a non-allow-listed host."""


class AllowlistTransport(httpx.AsyncBaseTransport):
    """Transport that delegates to an inner transport iff host is allowed."""

    def __init__(
        self,
        allowed_hosts: Iterable[str],
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._allowed = frozenset(h.lower() for h in allowed_hosts)
        self._inner = inner if inner is not None else httpx.AsyncHTTPTransport()

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return self._allowed

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host.lower()
        if host not in self._allowed:
            raise BlockedHostError(
                f"outbound host {host!r} not in allow-list; "
                f"configure it under [providers.*.upstream] first"
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def build_async_client(
    allowed_hosts: Iterable[str],
    timeout: float = 120.0,
    inner: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` that enforces the host allow-list."""
    transport = AllowlistTransport(allowed_hosts, inner=inner)
    return httpx.AsyncClient(transport=transport, timeout=timeout)
