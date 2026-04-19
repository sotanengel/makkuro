"""Tests for redaction.min_score configuration."""

from __future__ import annotations

import pytest

from makkuro.config import load_from_dict
from makkuro.proxy.redactor import Redactor
from makkuro.vault import MemoryVault


class TestMinScoreConfig:
    def test_default_zero(self):
        cfg = load_from_dict({})
        assert cfg.redaction.min_score == 0.0

    def test_load_from_dict(self):
        cfg = load_from_dict({"redaction": {"min_score": 0.9}})
        assert cfg.redaction.min_score == 0.9

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError, match="min_score"):
            load_from_dict({"redaction": {"min_score": 1.5}})

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="min_score"):
            load_from_dict({"redaction": {"min_score": -0.1}})


class TestMinScoreRedaction:
    def test_no_filter_at_zero(self):
        """Default min_score=0.0 lets everything through."""
        vault = MemoryVault()
        r = Redactor(vault, min_score=0.0)
        # Landline has score 0.85
        result = r.redact_text("call 03-1234-5678 now")
        assert "MAKKURO" in result

    def test_filters_below_threshold(self):
        """Detections scoring below min_score are dropped."""
        vault = MemoryVault()
        r = Redactor(vault, min_score=0.95)
        # JP_LANDLINE score=0.85, IPv4 score=0.85 → both filtered
        text = "call 03-1234-5678 or visit 10.0.0.1"
        result = r.redact_text(text)
        assert result == text  # nothing redacted

    def test_keeps_above_threshold(self):
        """Detections at or above min_score are kept."""
        vault = MemoryVault()
        r = Redactor(vault, min_score=0.95)
        # EMAIL score=0.99, JP_MOBILE score=0.98 → both kept
        text = "mail user@example.com phone 090-1234-5678"
        result = r.redact_text(text)
        assert "user@example.com" not in result
        assert "090-1234-5678" not in result

    def test_mixed_scores(self):
        """Only high-confidence detections are redacted with high threshold."""
        vault = MemoryVault()
        r = Redactor(vault, min_score=0.90)
        # EMAIL score=0.99 → kept, JP_LANDLINE score=0.85 → filtered
        text = "email user@test.io tel 03-1234-5678"
        result = r.redact_text(text)
        assert "user@test.io" not in result
        assert "03-1234-5678" in result  # not redacted

    def test_boundary_equal(self):
        """Detections exactly at min_score are kept (>=)."""
        vault = MemoryVault()
        r = Redactor(vault, min_score=0.85)
        # JP_LANDLINE score=0.85 → exactly at boundary → kept
        result = r.redact_text("call 03-1234-5678")
        assert "MAKKURO" in result
