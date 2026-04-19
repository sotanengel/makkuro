"""Tests for per-type detection counters in RedactionStats and /v1/status."""

from __future__ import annotations

from makkuro.proxy.redactor import RedactionStats, Redactor
from makkuro.vault import MemoryVault


class TestRedactionStatsByType:
    def test_empty_by_default(self):
        stats = RedactionStats()
        assert dict(stats.detections_by_type) == {}

    def test_counts_per_type(self):
        vault = MemoryVault()
        r = Redactor(vault)
        r.redact_text("email user@test.com phone 090-1234-5678")
        assert r.stats.detections_by_type["EMAIL"] == 1
        assert r.stats.detections_by_type["JP_MOBILE"] == 1
        assert r.stats.detections == 2

    def test_accumulates_across_calls(self):
        vault = MemoryVault()
        r = Redactor(vault)
        r.redact_text("user@a.com")
        r.redact_text("admin@b.com")
        assert r.stats.detections_by_type["EMAIL"] == 2
        assert r.stats.detections == 2

    def test_multiple_types(self):
        vault = MemoryVault()
        r = Redactor(vault)
        r.redact_text("〒100-0001 user@test.com 090-1111-2222")
        types = dict(r.stats.detections_by_type)
        assert "JP_ZIP" in types
        assert "EMAIL" in types
        assert "JP_MOBILE" in types


class TestStatusEndpointByType:
    def test_status_includes_by_type(self):
        from starlette.testclient import TestClient

        from makkuro.config import default_config
        from makkuro.proxy.app import build_app

        cfg = default_config()
        cfg.providers = {}  # no providers needed for status
        app = build_app(cfg)
        with TestClient(app) as client:
            r = client.get("/v1/status")
            assert r.status_code == 200
            body = r.json()
            assert "detections_by_type" in body
            assert isinstance(body["detections_by_type"], dict)
