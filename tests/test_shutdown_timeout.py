"""Tests for proxy.shutdown_timeout_sec configuration."""

from __future__ import annotations

import pytest

from makkuro.config import load_from_dict


class TestShutdownTimeoutConfig:
    def test_default_value(self):
        cfg = load_from_dict({})
        assert cfg.proxy.shutdown_timeout_sec == 5

    def test_load_from_dict(self):
        cfg = load_from_dict({"proxy": {"shutdown_timeout_sec": 10}})
        assert cfg.proxy.shutdown_timeout_sec == 10

    def test_zero_allowed(self):
        cfg = load_from_dict({"proxy": {"shutdown_timeout_sec": 0}})
        assert cfg.proxy.shutdown_timeout_sec == 0

    def test_max_allowed(self):
        cfg = load_from_dict({"proxy": {"shutdown_timeout_sec": 300}})
        assert cfg.proxy.shutdown_timeout_sec == 300

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="shutdown_timeout_sec"):
            load_from_dict({"proxy": {"shutdown_timeout_sec": -1}})

    def test_rejects_over_max(self):
        with pytest.raises(ValueError, match="shutdown_timeout_sec"):
            load_from_dict({"proxy": {"shutdown_timeout_sec": 301}})


class TestShutdownTimeoutServer:
    def test_passed_to_uvicorn(self, monkeypatch):
        """Verify shutdown_timeout_sec is forwarded to uvicorn.run."""
        captured = {}

        def fake_run(app, **kwargs):
            captured.update(kwargs)

        import makkuro.proxy.server as srv

        fake = type("FakeUvicorn", (), {"run": staticmethod(fake_run)})()
        monkeypatch.setattr(srv, "uvicorn", fake)

        cfg = load_from_dict({"proxy": {"shutdown_timeout_sec": 42}})
        cfg.providers = {}
        srv.run(cfg)
        assert captured["timeout_graceful_shutdown"] == 42
