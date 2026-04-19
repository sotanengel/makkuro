"""End-to-end SSE streaming test for the Anthropic Messages route."""

from __future__ import annotations

import json

import httpx
from starlette.testclient import TestClient

from makkuro.config import (
    AuditConfig,
    Config,
    ProviderConfig,
    ProxyConfig,
    RedactionConfig,
    SecurityConfig,
)
from makkuro.proxy.app import build_app


def _cfg() -> Config:
    return Config(
        proxy=ProxyConfig(),
        redaction=RedactionConfig(),
        providers={
            "anthropic": ProviderConfig(
                upstream="https://api.anthropic.com",
                protocol="anthropic",
            )
        },
        security=SecurityConfig(),
        audit=AuditConfig(enabled=False),
    )


def test_stream_rehydrates_placeholder_across_chunks():
    # The upstream mock echoes the placeholder back in an SSE frame split
    # across two raw chunks. The proxy must combine them and emit the
    # original email.
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        req_body = json.loads(request.content or b"{}")
        captured["body"] = req_body
        user_text = req_body["messages"][0]["content"][0]["text"]
        # Pull the placeholder the proxy minted for "foo@example.com".
        placeholder = next(tok for tok in user_text.split() if tok.startswith("<MAKKURO_"))
        mid = len(placeholder) // 2
        part_a = placeholder[:mid]
        part_b = placeholder[mid:]
        prefix = 'event: content_block_delta\ndata: {"delta":{"type":"text_delta","text":"hello '
        events = [
            f"{prefix}{part_a}",
            f'{part_b} world"}}}}\n\n',
        ]
        body = "".join(events).encode("utf-8")
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "text/event-stream"},
        )

    app = build_app(_cfg(), egress_transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        r = client.post(
            "/v1/messages",
            json={
                "model": "claude-test",
                "stream": True,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "send to foo@example.com"}],
                    }
                ],
            },
        )
        assert r.status_code == 200
        # The request forwarded upstream must have the redacted placeholder.
        fwd_text = captured["body"]["messages"][0]["content"][0]["text"]
        assert "foo@example.com" not in fwd_text
        assert "<MAKKURO_EMAIL_" in fwd_text
        # The streamed response must rehydrate the placeholder back to the
        # original email.
        assert "foo@example.com" in r.text


def test_stream_without_rehydrate_passes_through_unchanged():
    # When rehydrate is off the proxy still streams the response, just
    # without touching the text content.
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            b"event: content_block_delta\n"
            b'data: {"delta":{"type":"text_delta","text":"hi"}}\n\n'
        )
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "text/event-stream"},
        )

    cfg = _cfg()
    cfg.redaction.rehydrate = False
    app = build_app(cfg, egress_transport=httpx.MockTransport(handler))
    with TestClient(app) as client:
        r = client.post(
            "/v1/messages",
            json={
                "model": "x",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 200
        assert "text_delta" in r.text
