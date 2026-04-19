"""Tests for redaction.response_redaction configuration."""

from __future__ import annotations

import httpx
from starlette.testclient import TestClient

from makkuro.config import Config, ProviderConfig, ProxyConfig, RedactionConfig, SecurityConfig
from makkuro.proxy.app import build_app


def _config(response_redaction: bool = False) -> Config:
    return Config(
        proxy=ProxyConfig(),
        redaction=RedactionConfig(response_redaction=response_redaction),
        providers={
            "anthropic": ProviderConfig(
                upstream="https://api.anthropic.com",
                protocol="anthropic",
            )
        },
        security=SecurityConfig(),
    )


def _mock_transport(reply_text: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
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

    return httpx.MockTransport(handler)


def _post_message(client, text: str = "hello"):
    return client.post(
        "/v1/messages",
        json={
            "model": "claude-test",
            "messages": [{"role": "user", "content": text}],
        },
    )


class TestResponseRedaction:
    def test_off_by_default(self):
        from makkuro.config import load_from_dict

        cfg = load_from_dict({})
        assert cfg.redaction.response_redaction is False

    def test_load_from_dict(self):
        from makkuro.config import load_from_dict

        cfg = load_from_dict({"redaction": {"response_redaction": True}})
        assert cfg.redaction.response_redaction is True

    def test_response_not_redacted_when_off(self):
        transport = _mock_transport("連絡先は test@example.com です")
        app = build_app(_config(response_redaction=False), egress_transport=transport)
        with TestClient(app) as client:
            r = _post_message(client)
            assert r.status_code == 200
            text = r.json()["content"][0]["text"]
            assert "test@example.com" in text

    def test_response_redacted_when_on(self):
        transport = _mock_transport("連絡先は test@example.com です")
        app = build_app(_config(response_redaction=True), egress_transport=transport)
        with TestClient(app) as client:
            r = _post_message(client)
            assert r.status_code == 200
            text = r.json()["content"][0]["text"]
            assert "test@example.com" not in text
            assert "MAKKURO" in text

    def test_response_redacts_phone(self):
        transport = _mock_transport("電話番号は090-1234-5678です")
        app = build_app(_config(response_redaction=True), egress_transport=transport)
        with TestClient(app) as client:
            r = _post_message(client)
            text = r.json()["content"][0]["text"]
            assert "090-1234-5678" not in text

    def test_no_pii_in_response_unchanged(self):
        transport = _mock_transport("問題ありません")
        app = build_app(_config(response_redaction=True), egress_transport=transport)
        with TestClient(app) as client:
            r = _post_message(client)
            text = r.json()["content"][0]["text"]
            assert text == "問題ありません"
