"""Starlette application factory for the redaction proxy.

Only non-streaming Anthropic ``POST /v1/messages`` is wired up in Phase 1.
SSE streaming and MCP deep-redact arrive in Phase 3.

The app keeps request and response handling symmetric: we decode into the
canonical form, run the redactor, re-encode into the provider payload, relay
it upstream via an allow-listed httpx client, optionally rehydrate
placeholders in the response, and write the final JSON back to the client.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from makkuro.config import Config
from makkuro.protocol import AnthropicAdapter, ProtocolAdapter
from makkuro.proxy.egress import BlockedHostError, build_async_client
from makkuro.proxy.redactor import Redactor
from makkuro.vault import MemoryVault
from makkuro.vault.base import Vault

logger = logging.getLogger("makkuro.proxy")


HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "host",
    }
)


def _filter_forward_headers(headers: dict[str, str], strip_host: bool = True) -> dict[str, str]:
    out = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        if strip_host and lk == "host":
            continue
        out[k] = v
    return out


async def _proxy_anthropic_messages(
    request: Request,
) -> Response:
    cfg: Config = request.app.state.config
    adapter: ProtocolAdapter = request.app.state.adapters["anthropic"]
    redactor: Redactor = request.app.state.redactor
    client: httpx.AsyncClient = request.app.state.egress

    provider = cfg.providers.get("anthropic")
    if provider is None or not provider.enabled:
        return JSONResponse({"error": "anthropic provider disabled"}, status_code=503)

    raw_body = await request.body()
    max_bytes = cfg.proxy.max_body_mb * 1024 * 1024
    if len(raw_body) > max_bytes:
        return JSONResponse({"error": "request body too large"}, status_code=413)

    try:
        body = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)

    canonical = adapter.decode_request(body)
    try:
        redactor.redact_request(canonical)
    except Exception as e:  # fail-safe per spec §6.10
        logger.exception("redaction failed; refusing to forward", exc_info=e)
        if cfg.redaction.mode == "warn":
            # warn mode lets the original go through untouched
            encoded = body
        else:
            return JSONResponse(
                {"error": "redaction failed; request refused"},
                status_code=500,
            )
    else:
        encoded = adapter.encode_request(canonical, body)

    upstream_url = provider.upstream.rstrip("/") + request.url.path
    if request.url.query:
        upstream_url += "?" + request.url.query

    upstream_headers = _filter_forward_headers(dict(request.headers))

    try:
        upstream = await client.post(
            upstream_url,
            content=json.dumps(encoded).encode("utf-8"),
            headers={**upstream_headers, "content-type": "application/json"},
        )
    except BlockedHostError as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    except httpx.RequestError as e:
        return JSONResponse({"error": f"upstream error: {e}"}, status_code=502)

    resp_headers = _filter_forward_headers(dict(upstream.headers))
    content_type = upstream.headers.get("content-type", "")

    if upstream.status_code >= 400 or "application/json" not in content_type:
        # Pass error / non-JSON bodies through untouched.
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=content_type or None,
        )

    try:
        resp_body: dict[str, Any] = json.loads(upstream.content or b"{}")
    except json.JSONDecodeError:
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=content_type,
        )

    if cfg.redaction.rehydrate:
        edits = adapter.extract_response_text(resp_body)
        if edits:
            new_edits = [(path, redactor.rehydrate_text(text)) for path, text in edits]
            resp_body = adapter.apply_response_text(resp_body, new_edits)

    return JSONResponse(resp_body, status_code=upstream.status_code, headers=resp_headers)


async def _healthz(_: Request) -> Response:
    return JSONResponse({"status": "ok"})


async def _status(request: Request) -> Response:
    cfg: Config = request.app.state.config
    redactor: Redactor = request.app.state.redactor
    return JSONResponse(
        {
            "status": "ok",
            "bind": cfg.proxy.bind,
            "port": cfg.proxy.port,
            "mode": cfg.redaction.mode,
            "rehydrate": cfg.redaction.rehydrate,
            "upstream_hosts": sorted(cfg.upstream_hosts),
            "detections": redactor.stats.detections,
            "rehydrated": redactor.stats.rehydrated,
        }
    )


def build_app(
    config: Config,
    vault: Vault | None = None,
    redactor: Redactor | None = None,
    egress_transport: httpx.AsyncBaseTransport | None = None,
) -> Starlette:
    """Build the Starlette proxy application.

    Callers can inject ``egress_transport`` to route upstream calls through a
    mock (used by the test suite) or through a real ``httpx`` transport.
    """
    vault = vault if vault is not None else MemoryVault()
    redactor = redactor if redactor is not None else Redactor(vault)
    egress = build_async_client(
        allowed_hosts=config.upstream_hosts,
        timeout=float(config.proxy.request_timeout_sec),
        inner=egress_transport,
    )

    app = Starlette(
        routes=[
            Route("/healthz", _healthz, methods=["GET"]),
            Route("/v1/status", _status, methods=["GET"]),
            Route("/v1/messages", _proxy_anthropic_messages, methods=["POST"]),
        ]
    )
    app.state.config = config
    app.state.adapters = {"anthropic": AnthropicAdapter()}
    app.state.redactor = redactor
    app.state.vault = vault
    app.state.egress = egress

    async def _close_egress() -> None:
        await egress.aclose()

    app.add_event_handler("shutdown", _close_egress)
    return app
