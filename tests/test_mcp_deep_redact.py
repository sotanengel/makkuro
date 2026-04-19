"""MCP deep-redact tests: tool_use JSON input and tool_result output."""

from __future__ import annotations

import json

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
from makkuro.proxy.redactor import Redactor
from makkuro.vault import MemoryVault


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


class TestRedactorDeepRedact:
    def test_nested_dict_and_list(self):
        r = Redactor(MemoryVault(), audit=AuditWriter(path=None, enabled=False))
        payload = {
            "command": "send",
            "args": {
                "to": "a@b.jp",
                "alternates": ["b@c.jp", "c@d.jp"],
                "note": "no secrets here",
            },
        }
        out = r._redact_json(payload)
        s = json.dumps(out)
        assert "a@b.jp" not in s
        assert "b@c.jp" not in s
        assert "c@d.jp" not in s
        assert "no secrets here" in s  # plain strings without entities pass through

    def test_preserves_control_keys(self):
        r = Redactor(MemoryVault(), audit=AuditWriter(path=None, enabled=False))
        payload = {
            "jsonrpc": "2.0",
            "id": "call_123",
            "method": "foo@example.com",  # structurally a string, but identifies
            # the RPC method, so the redactor skips it rather than mangling the
            # protocol.
            "params": {"email": "user@example.com"},
        }
        out = r._redact_json(payload)
        assert out["jsonrpc"] == "2.0"
        assert out["id"] == "call_123"
        assert out["method"] == "foo@example.com"
        assert "user@example.com" not in json.dumps(out["params"])


class TestToolUseRedactedEndToEnd:
    def test_anthropic_tool_use_is_redacted(self):
        captured = {}

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

        app = build_app(_cfg(), egress_transport=httpx.MockTransport(handler))
        with TestClient(app) as client:
            client.post(
                "/v1/messages",
                json={
                    "model": "x",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "tu_1",
                                    "name": "send_email",
                                    "input": {
                                        "to": "victim@example.com",
                                        "body": "mobile 090-1234-5678",
                                    },
                                }
                            ],
                        }
                    ],
                },
            )
        fwd = captured["body"]
        content = fwd["messages"][0]["content"][0]
        assert content["name"] == "send_email"
        assert "victim@example.com" not in json.dumps(content["input"])
        assert "090-1234-5678" not in json.dumps(content["input"])
