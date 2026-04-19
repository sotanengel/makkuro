from __future__ import annotations

from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.detectors.jp_pii import (
    JPCreditCardDetector,
    JPLandlineDetector,
    JPMobileDetector,
    JPMyNumberDetector,
    JPZipDetector,
    luhn_valid,
    mynumber_check_valid,
)
from makkuro.detectors.regex_base import EmailDetector
from makkuro.pipeline import run_detectors


def _types(text: str) -> list[str]:
    return sorted(d.type for d in run_detectors(DEFAULT_DETECTORS, text))


class TestEmail:
    def test_basic(self):
        hits = EmailDetector().scan("contact me at foo@example.com please")
        assert len(hits) == 1
        assert hits[0].value == "foo@example.com"
        assert hits[0].type == "EMAIL"

    def test_multiple(self):
        hits = EmailDetector().scan("a@b.jp and c.d-e@sub.example.org")
        assert [h.value for h in hits] == ["a@b.jp", "c.d-e@sub.example.org"]

    def test_no_match(self):
        assert EmailDetector().scan("not an email @ example") == []


class TestMobile:
    def test_hyphenated(self):
        hits = JPMobileDetector().scan("090-1234-5678")
        assert len(hits) == 1
        assert hits[0].value == "090-1234-5678"

    def test_contiguous(self):
        hits = JPMobileDetector().scan("08012345678")
        assert len(hits) == 1

    def test_all_prefixes(self):
        for pre in ("070", "080", "090"):
            assert JPMobileDetector().scan(f"{pre}-0000-1111")


class TestLandline:
    def test_basic(self):
        hits = JPLandlineDetector().scan("03-1234-5678")
        assert len(hits) == 1

    def test_rejects_mobile_prefix(self):
        assert JPLandlineDetector().scan("090-1234-5678") == []

    def test_short_digits_rejected(self):
        assert JPLandlineDetector().scan("12-3456") == []


class TestZip:
    def test_with_symbol(self):
        hits = JPZipDetector().scan("〒100-0001")
        assert len(hits) == 1

    def test_without_symbol(self):
        hits = JPZipDetector().scan("zip 150-0002 here")
        assert len(hits) == 1


class TestCreditCard:
    def test_luhn_valid(self):
        assert luhn_valid("4111111111111111")
        assert luhn_valid("5555555555554444")
        assert luhn_valid("378282246310005")

    def test_luhn_invalid(self):
        assert not luhn_valid("4111111111111112")
        assert not luhn_valid("1234567890123456")

    def test_detector_rejects_invalid(self):
        assert JPCreditCardDetector().scan("1234567890123456") == []

    def test_detector_accepts_valid(self):
        hits = JPCreditCardDetector().scan("Card: 4111-1111-1111-1111 end")
        assert len(hits) == 1


class TestMyNumber:
    def test_checksum_valid(self):
        assert mynumber_check_valid("111111111118")
        assert mynumber_check_valid("123456789016")

    def test_checksum_invalid(self):
        assert not mynumber_check_valid("123456789012")
        assert not mynumber_check_valid("111111111111")

    def test_detector(self):
        hits = JPMyNumberDetector().scan("番号 111111111118 です")
        assert len(hits) == 1


class TestPipeline:
    def test_mixed(self):
        text = "〒100-0001, email=user@example.com, card=4111111111111111"
        types = _types(text)
        assert "EMAIL" in types
        assert "JP_ZIP" in types
        assert "JP_CREDIT_CARD" in types

    def test_resolves_overlap(self):
        # mobile 090-1234-5678 would also match a 10-digit landline if
        # not for the mobile-prefix rejection; make sure only MOBILE wins.
        text = "連絡先 090-1234-5678 まで"
        types = _types(text)
        assert types == ["JP_MOBILE"]

    def test_hard_negatives(self):
        assert _types("本日は 2024-01-15 です") == []
        assert _types("注文番号 123456789012 を控えて") == []
        assert _types("カードっぽい 1234567890123456 はダミー") == []
