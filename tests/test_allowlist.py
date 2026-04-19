from __future__ import annotations

from makkuro.allowlist import AllowList
from makkuro.detectors.base import Detection


def _email(value: str) -> Detection:
    return Detection(
        type="EMAIL", start=0, end=len(value), score=0.99, detector="email", value=value
    )


def _other(value: str, kind: str = "JP_MOBILE") -> Detection:
    return Detection(
        type=kind, start=0, end=len(value), score=0.95, detector="x", value=value
    )


class TestAllowList:
    def test_empty_keeps_everything(self):
        al = AllowList()
        items = [_email("a@b.jp"), _other("090-0000-0000")]
        assert al.filter(items) == items

    def test_email_exact(self):
        al = AllowList.from_dict({"emails": ["noreply@example.com"]})
        kept = al.filter([_email("noreply@example.com"), _email("real@example.com")])
        assert [d.value for d in kept] == ["real@example.com"]

    def test_email_case_insensitive(self):
        al = AllowList.from_dict({"emails": ["Noreply@Example.com"]})
        kept = al.filter([_email("noreply@EXAMPLE.com")])
        assert kept == []

    def test_domain(self):
        al = AllowList.from_dict({"domains": ["example.com"]})
        kept = al.filter([_email("a@example.com"), _email("b@example.org")])
        assert [d.value for d in kept] == ["b@example.org"]

    def test_pattern_matches_any_type(self):
        al = AllowList.from_dict({"patterns": [r"^090-0000-"]})
        kept = al.filter(
            [
                _other("090-0000-1111"),
                _other("090-1234-5678"),
            ]
        )
        assert [d.value for d in kept] == ["090-1234-5678"]

    def test_invalid_pattern_raises(self):
        import pytest

        with pytest.raises(ValueError):
            AllowList.from_dict({"patterns": [r"(unclosed"]})
