"""Phase 2 multi-provider proxy tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
from starlette.testclient import TestClient

from makkuro.audit import AuditWriter
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
            ),
            "openai": ProviderConfig(
                upstream="https://api.openai.com",
                protocol="openai",
            ),
            "gemini": ProviderConfig(
                upstream="https://generativelanguage.googleapis.com",
                protocol="gemini",
            ),
        },
        security=SecurityConfig(),
        audit=AuditConfig(enabled=False),
    )


def _mock(handler):
    return httpx.MockTransport(handler)


class TestOpenAIRoute:
    def test_redacts_email_in_chat_completions(self):
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content or b"{}")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "ok"}}
                    ]
                },
                headers={"content-type": "application/json"},
            )

        app = build_app(_cfg(), egress_transport=_mock(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "user", "content": "email foo@example.com"}
                    ],
                },
            )
            assert r.status_code == 200
            fwd = captured["body"]
            assert "foo@example.com" not in json.dumps(fwd)
            assert "<MAKKURO_EMAIL_" in json.dumps(fwd)
            assert captured["url"].startswith("https://api.openai.com")


class TestGeminiRoute:
    def test_redacts_phone_in_generate_content(self):
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content or b"{}")
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [{"text": "ok"}],
                            }
                        }
                    ]
                },
                headers={"content-type": "application/json"},
            )

        app = build_app(_cfg(), egress_transport=_mock(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1beta/models/gemini-pro:generateContent",
                json={
                    "contents": [
                        {"role": "user", "parts": [{"text": "call 090-1234-5678"}]}
                    ]
                },
            )
            assert r.status_code == 200
            fwd = captured["body"]
            text = fwd["contents"][0]["parts"][0]["text"]
            assert "090-1234-5678" not in text
            assert "<MAKKURO_JP_MOBILE_" in text
            assert captured["url"].startswith("https://generativelanguage.googleapis.com")


class TestAuditIntegration:
    def test_audit_records_redaction_events(self):
        def handler(request: httpx.Request) -> httpx.Response:
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

        audit = AuditWriter(path=None, enabled=True)
        app = build_app(_cfg(), egress_transport=_mock(handler), audit=audit)
        with TestClient(app) as client:
            client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [{"role": "user", "content": "foo@example.com"}],
                },
            )
        events = audit.buffered()
        assert any(e["event"] == "redact" for e in events)
        # No plaintext should appear anywhere in the audit log.
        dumped = json.dumps(events)
        assert "foo@example.com" not in dumped
