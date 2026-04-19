"""Starlette application factory for the redaction proxy.

Phase 2 wires up three non-streaming providers:

* Anthropic Messages (``POST /v1/messages``)
* OpenAI Chat / Responses (``POST /v1/chat/completions``, ``POST /v1/responses``)
* Google Gemini (``POST /v1beta/models/{model}:generateContent``)

SSE streaming and MCP deep-redact arrive in Phase 3. Each request follows
the same pipeline: JSON decode -> adapter.decode_request -> redactor ->
adapter.encode_request -> httpx POST (allow-listed) -> on JSON 2xx,
adapter.extract_response_text + redactor.rehydrate_text -> JSON response.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from makkuro.allowlist import AllowList
from makkuro.audit import AuditWriter
from makkuro.config import Config
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.detectors.custom import make_custom_detectors
from makkuro.protocol import (
    AnthropicAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    ProtocolAdapter,
)
from makkuro.proxy.egress import BlockedHostError, build_async_client
from makkuro.proxy.redactor import Redactor
from makkuro.proxy.sse import SSERehydrator
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


def _filter_forward_headers(
    headers: dict[str, str],
    strip_host: bool = True,
) -> dict[str, str]:
    out = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in HOP_BY_HOP_HEADERS:
            continue
        if strip_host and lk == "host":
            continue
        out[k] = v
    return out


async def _relay(
    request: Request,
    provider_key: str,
) -> Response:
    cfg: Config = request.app.state.config
    adapter: ProtocolAdapter = request.app.state.adapters[provider_key]
    redactor: Redactor = request.app.state.redactor
    client: httpx.AsyncClient = request.app.state.egress

    provider = cfg.providers.get(provider_key)
    if provider is None or not provider.enabled:
        return JSONResponse(
            {"error": f"{provider_key} provider disabled"},
            status_code=503,
        )

    raw_body = await request.body()
    max_bytes = cfg.proxy.max_body_mb * 1024 * 1024
    if len(raw_body) > max_bytes:
        return JSONResponse({"error": "request body too large"}, status_code=413)

    try:
        body = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as e:
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    redactor.bind_request(request_id)

    canonical = adapter.decode_request(body)
    try:
        redactor.redact_request(canonical)
    except Exception as e:  # fail-safe per spec §6.10
        logger.exception("redaction failed; refusing to forward", exc_info=e)
        if cfg.redaction.mode == "warn":
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
    outbound_headers = {
        **upstream_headers,
        "content-type": "application/json",
        "x-request-id": request_id,
    }
    outbound_content = json.dumps(encoded).encode("utf-8")

    streaming = bool(encoded.get("stream")) or "text/event-stream" in request.headers.get(
        "accept", ""
    )

    if streaming:
        return await _relay_stream(
            client=client,
            cfg=cfg,
            redactor=redactor,
            url=upstream_url,
            headers=outbound_headers,
            content=outbound_content,
        )

    try:
        upstream = await client.post(
            upstream_url,
            content=outbound_content,
            headers=outbound_headers,
        )
    except BlockedHostError as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    except httpx.RequestError as e:
        return JSONResponse({"error": f"upstream error: {e}"}, status_code=502)

    resp_headers = _filter_forward_headers(dict(upstream.headers))
    content_type = upstream.headers.get("content-type", "")

    if upstream.status_code >= 400 or "application/json" not in content_type:
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

    if cfg.redaction.response_redaction:
        resp_edits = adapter.extract_response_text(resp_body)
        if resp_edits:
            redacted_edits = [(path, redactor.redact_text(text)) for path, text in resp_edits]
            resp_body = adapter.apply_response_text(resp_body, redacted_edits)

    return JSONResponse(resp_body, status_code=upstream.status_code, headers=resp_headers)


async def _relay_stream(
    client: httpx.AsyncClient,
    cfg: Config,
    redactor: Redactor,
    url: str,
    headers: dict[str, str],
    content: bytes,
) -> Response:
    """Relay an SSE stream upstream -> client with per-chunk rehydration.

    The look-back buffer in :class:`SSERehydrator` guarantees a placeholder
    split across two SSE chunks is never emitted half-rewritten.
    """
    rehydrator = SSERehydrator(redactor.mint) if cfg.redaction.rehydrate else None

    async def _body_iter():
        try:
            async with client.stream(
                "POST", url, content=content, headers=headers
            ) as upstream:
                if upstream.status_code >= 400:
                    # On error, read the full body and pass through unchanged.
                    err_bytes = await upstream.aread()
                    yield err_bytes
                    return
                async for chunk in upstream.aiter_bytes():
                    if rehydrator is None:
                        yield chunk
                        continue
                    try:
                        text = chunk.decode("utf-8")
                    except UnicodeDecodeError:
                        yield chunk
                        continue
                    out = rehydrator.feed(text)
                    if out:
                        yield out.encode("utf-8")
                if rehydrator is not None:
                    tail = rehydrator.flush()
                    if tail:
                        yield tail.encode("utf-8")
        except BlockedHostError as e:
            yield json.dumps({"error": str(e)}).encode("utf-8")
        except httpx.RequestError as e:
            yield json.dumps({"error": f"upstream error: {e}"}).encode("utf-8")

    return StreamingResponse(
        _body_iter(),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache"},
    )


async def _proxy_anthropic(request: Request) -> Response:
    return await _relay(request, "anthropic")


async def _proxy_openai(request: Request) -> Response:
    return await _relay(request, "openai")


async def _proxy_gemini(request: Request) -> Response:
    return await _relay(request, "gemini")


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
            "detections_by_type": dict(redactor.stats.detections_by_type),
            "rehydrated": redactor.stats.rehydrated,
        }
    )


def build_app(
    config: Config,
    vault: Vault | None = None,
    redactor: Redactor | None = None,
    egress_transport: httpx.AsyncBaseTransport | None = None,
    audit: AuditWriter | None = None,
) -> Starlette:
    """Build the Starlette proxy application.

    Callers can inject ``egress_transport`` (typically an ``httpx.MockTransport``
    from the test suite) and ``audit`` (an in-memory ``AuditWriter`` for
    tests). Both default to a real allow-listed httpx transport and a no-op
    writer respectively.
    """
    vault = vault if vault is not None else MemoryVault()
    if audit is None:
        if config.audit.enabled:
            import os
            from pathlib import Path

            if config.audit.path:
                audit_path = Path(config.audit.path)
            else:
                state_dir = Path(
                    os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
                )
                audit_path = state_dir / "makkuro" / "audit.jsonl"
            audit = AuditWriter(path=audit_path, enabled=True)
        else:
            audit = AuditWriter(path=None, enabled=False)
    if redactor is None:
        # Compose the detector chain: built-ins + any user-defined patterns.
        detectors = list(DEFAULT_DETECTORS)
        if config.redaction.custom_patterns:
            detectors.extend(make_custom_detectors(config.redaction.custom_patterns))
        allow_list = AllowList.from_dict(config.redaction.allow_list)
        redactor = Redactor(
            vault,
            detectors=detectors,
            audit=audit,
            allow_list=allow_list,
            min_score=config.redaction.min_score,
        )
    egress = build_async_client(
        allowed_hosts=config.upstream_hosts,
        timeout=float(config.proxy.request_timeout_sec),
        inner=egress_transport,
    )

    routes = [
        Route("/healthz", _healthz, methods=["GET"]),
        Route("/v1/status", _status, methods=["GET"]),
        Route("/v1/messages", _proxy_anthropic, methods=["POST"]),
        Route("/v1/chat/completions", _proxy_openai, methods=["POST"]),
        Route("/v1/responses", _proxy_openai, methods=["POST"]),
        Route("/v1beta/models/{rest:path}", _proxy_gemini, methods=["POST"]),
        Route("/v1/models/{rest:path}", _proxy_gemini, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.state.config = config
    app.state.adapters = {
        "anthropic": AnthropicAdapter(),
        "openai": OpenAIAdapter(),
        "gemini": GeminiAdapter(),
    }
    app.state.redactor = redactor
    app.state.vault = vault
    app.state.egress = egress
    app.state.audit = audit

    async def _close_egress() -> None:
        await egress.aclose()

    app.add_event_handler("shutdown", _close_egress)
    return app
