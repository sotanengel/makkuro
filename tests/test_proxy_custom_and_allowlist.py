"""Proxy-level integration: custom patterns + allow list."""

from __future__ import annotations

import json
from typing import Any

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


def _cfg(custom_patterns=None, allow_list=None) -> Config:
    return Config(
        proxy=ProxyConfig(),
        redaction=RedactionConfig(
            custom_patterns=custom_patterns or {},
            allow_list=allow_list or {},
        ),
        providers={
            "anthropic": ProviderConfig(
                upstream="https://api.anthropic.com",
                protocol="anthropic",
            )
        },
        security=SecurityConfig(),
        audit=AuditConfig(enabled=False),
    )


def _handler() -> tuple[Any, dict[str, Any]]:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return httpx.Response(
            200,
            json={
                "id": "m",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
                "model": "x",
                "stop_reason": "end_turn",
            },
            headers={"content-type": "application/json"},
        )

    return handler, captured


class TestCustomPatterns:
    def test_employee_id_redacted(self):
        handler, captured = _handler()
        cfg = _cfg(custom_patterns={"employee_id": r"EMP-\d{6}"})
        app = build_app(cfg, egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [
                        {"role": "user", "content": "issue assigned to EMP-123456 today"}
                    ],
                },
            )
            assert r.status_code == 200
            text = captured["body"]["messages"][0]["content"][0]["text"]
            assert "EMP-123456" not in text
            assert "<MAKKURO_EMPLOYEE_ID_" in text


class TestAllowListInProxy:
    def test_whitelisted_email_passes_through(self):
        handler, captured = _handler()
        cfg = _cfg(allow_list={"emails": ["noreply@example.com"]})
        app = build_app(cfg, egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [
                        {
                            "role": "user",
                            "content": "from noreply@example.com to alice@example.com",
                        }
                    ],
                },
            )
            assert r.status_code == 200
            text = captured["body"]["messages"][0]["content"][0]["text"]
            # Allow-listed value passes verbatim; the other email is redacted.
            assert "noreply@example.com" in text
            assert "alice@example.com" not in text
            assert "<MAKKURO_EMAIL_" in text
