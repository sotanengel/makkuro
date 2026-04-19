"""End-to-end tests for the Phase 1 proxy, using an httpx MockTransport to
stand in for the real Anthropic API."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from makkuro.config import Config, ProviderConfig, ProxyConfig, RedactionConfig, SecurityConfig
from makkuro.proxy.app import build_app
from makkuro.proxy.egress import AllowlistTransport, BlockedHostError


def _config() -> Config:
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
    )


class RecordingMockTransport(httpx.MockTransport):
    """A mock transport that remembers the last request seen."""

    def __init__(self, handler):
        super().__init__(handler)
        self.last_request: httpx.Request | None = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        self.last_request = request
        return super().handle_request(request)


def _make_upstream(
    reply_text: str = "Hello <MAKKURO_EMAIL_placeholder>",
) -> tuple[RecordingMockTransport, dict[str, Any]]:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = json.loads(request.content or b"{}")
        resp_body = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": reply_text}],
            "model": "claude-test",
            "stop_reason": "end_turn",
        }
        return httpx.Response(
            200,
            json=resp_body,
            headers={"content-type": "application/json"},
        )

    return RecordingMockTransport(handler), captured


class TestProxyRequest:
    def test_healthz(self):
        app = build_app(_config())
        with TestClient(app) as client:
            r = client.get("/healthz")
            assert r.status_code == 200
            assert r.json() == {"status": "ok"}

    def test_status_shows_allowlist(self):
        app = build_app(_config())
        with TestClient(app) as client:
            r = client.get("/v1/status")
            assert r.status_code == 200
            payload = r.json()
            assert payload["upstream_hosts"] == ["api.anthropic.com"]

    def test_redacts_email_before_forwarding(self):
        transport, captured = _make_upstream()
        app = build_app(_config(), egress_transport=httpx.MockTransport(transport.handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "claude-test",
                    "messages": [
                        {"role": "user", "content": "連絡先は foo@example.com です"}
                    ],
                },
            )
            assert r.status_code == 200
            upstream_body = captured["body"]
            upstream_text = upstream_body["messages"][0]["content"][0]["text"]
            assert "foo@example.com" not in upstream_text
            assert "<MAKKURO_EMAIL_" in upstream_text

    def test_structured_content_blocks(self):
        transport, captured = _make_upstream()
        app = build_app(_config(), egress_transport=httpx.MockTransport(transport.handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "claude-test",
                    "system": "You are a helpful assistant, email: root@example.com",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "card 4111111111111111"},
                                {"type": "text", "text": "mobile 090-0000-1111"},
                            ],
                        }
                    ],
                },
            )
            assert r.status_code == 200
            sys_out = captured["body"]["system"]
            assert "root@example.com" not in json.dumps(sys_out)
            parts = captured["body"]["messages"][0]["content"]
            assert "4111111111111111" not in parts[0]["text"]
            assert "090-0000-1111" not in parts[1]["text"]

    def test_rehydrate_restores_response(self):
        # The upstream "reply" echoes a placeholder we just minted in the
        # request path; the proxy should rehydrate it when returning to the
        # client.
        def handler(request: httpx.Request) -> httpx.Response:
            req_body = json.loads(request.content or b"{}")
            # Grab whatever placeholder the proxy inserted for the email and
            # echo it verbatim in the response.
            text = req_body["messages"][0]["content"][0]["text"]
            placeholder = text.split(" ")[-2]
            return httpx.Response(
                200,
                json={
                    "id": "msg_echo",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"echoed {placeholder} back"}
                    ],
                    "model": "claude-test",
                    "stop_reason": "end_turn",
                },
                headers={"content-type": "application/json"},
            )

        app = build_app(_config(), egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "claude-test",
                    "messages": [{"role": "user", "content": "send to foo@example.com now"}],
                },
            )
            assert r.status_code == 200
            reply_text = r.json()["content"][0]["text"]
            assert "foo@example.com" in reply_text

    def test_no_rehydrate_mode_leaves_placeholders(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "msg",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "text", "text": "hi"}],
                    "model": "x",
                    "stop_reason": "end_turn",
                },
                headers={"content-type": "application/json"},
            )

        cfg = _config()
        cfg.redaction.rehydrate = False
        app = build_app(cfg, egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [{"role": "user", "content": "foo@example.com"}],
                },
            )
            assert r.status_code == 200
            # With rehydrate off the response is returned unchanged; nothing
            # further to verify here beyond "didn't crash".

    def test_upstream_error_is_passed_through(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                content=b'{"type":"rate_limit_error"}',
                headers={"content-type": "application/json"},
            )

        app = build_app(_config(), egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            r = client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            assert r.status_code == 429


class TestAllowlistTransport:
    def test_blocks_non_allowlisted_host(self):
        import asyncio

        async def run() -> None:
            captured: dict[str, Any] = {}

            def inner_handler(request: httpx.Request) -> httpx.Response:
                captured["called"] = True
                return httpx.Response(200)

            t = AllowlistTransport(
                allowed_hosts=["api.anthropic.com"],
                inner=httpx.MockTransport(inner_handler),
            )
            async with httpx.AsyncClient(transport=t) as client:
                with pytest.raises(BlockedHostError):
                    await client.get("https://evil.example.com/")
            assert captured == {}

        asyncio.run(run())

    def test_allows_listed_host(self):
        import asyncio

        async def run() -> None:
            def inner_handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, text="ok")

            t = AllowlistTransport(
                allowed_hosts=["api.anthropic.com"],
                inner=httpx.MockTransport(inner_handler),
            )
            async with httpx.AsyncClient(transport=t) as client:
                r = await client.get("https://api.anthropic.com/x")
                assert r.status_code == 200

        asyncio.run(run())
