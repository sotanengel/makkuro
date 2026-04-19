"""Japanese-specific PII detectors (Phase 0 baseline)."""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

# Mobile: 070/080/090-XXXX-XXXX (hyphen optional, one space allowed)
MOBILE_RE = re.compile(
    r"(?<!\d)"
    r"0[789]0[-\s]?\d{4}[-\s]?\d{4}"
    r"(?!\d)"
)

# Landline: 0 + 1-4 digit area code + dashes + local number; total 10 digits
# Accepts forms like 03-1234-5678, 0120-123-456, 0467-12-3456
LANDLINE_RE = re.compile(
    r"(?<!\d)"
    r"0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}"
    r"(?!\d)"
)

# Japanese postal code: 〒?NNN-NNNN (hyphen optional)
ZIP_RE = re.compile(
    r"(?:〒\s?)?"
    r"(?<!\d)"
    r"\d{3}[-\s]?\d{4}"
    r"(?!\d)"
)

# Credit card number: 13-19 digits with dashes/spaces (grouped 4-4-4-4 typical)
CREDIT_CARD_RE = re.compile(
    r"(?<!\d)"
    r"(?:\d[-\s]?){12,18}\d"
    r"(?!\d)"
)

# My Number: 12 contiguous digits
MYNUMBER_RE = re.compile(
    r"(?<!\d)"
    r"\d{12}"
    r"(?!\d)"
)


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def luhn_valid(digits: str) -> bool:
    """Return True if ``digits`` (only digit chars) passes the Luhn checksum."""
    if not digits or not digits.isdigit():
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        n = ord(ch) - 48
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Weights used by Japan's My Number checksum algorithm (positions 1..11).
# Reference: 行政手続における特定の個人を識別するための番号の利用等に関する法律施行令 第八条
_MYNUMBER_WEIGHTS = [6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


def mynumber_check_valid(digits: str) -> bool:
    """Validate the 12-digit My Number checksum."""
    if len(digits) != 12 or not digits.isdigit():
        return False
    body = [ord(c) - 48 for c in digits[:11]]
    check = ord(digits[11]) - 48
    s = sum(d * w for d, w in zip(body[::-1], _MYNUMBER_WEIGHTS, strict=False))
    rem = s % 11
    expected = 0 if rem <= 1 else 11 - rem
    return expected == check


class JPMobileDetector:
    name = "jp_mobile"
    entity_type = "JP_MOBILE"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in MOBILE_RE.finditer(text):
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.98,
                    detector=self.name,
                    value=m.group(0),
                )
            )
        return out


class JPLandlineDetector:
    name = "jp_landline"
    entity_type = "JP_LANDLINE"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in LANDLINE_RE.finditer(text):
            raw = m.group(0)
            digits = _digits_only(raw)
            # Must be exactly 10 digits and start with 0, and not a mobile prefix.
            if len(digits) != 10:
                continue
            if digits.startswith(("070", "080", "090")):
                continue
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.85,
                    detector=self.name,
                    value=raw,
                )
            )
        return out


class JPZipDetector:
    name = "jp_zip"
    entity_type = "JP_ZIP"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in ZIP_RE.finditer(text):
            raw = m.group(0)
            digits = _digits_only(raw)
            if len(digits) != 7:
                continue
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.9,
                    detector=self.name,
                    value=raw,
                )
            )
        return out


class JPCreditCardDetector:
    name = "jp_credit_card"
    entity_type = "JP_CREDIT_CARD"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in CREDIT_CARD_RE.finditer(text):
            raw = m.group(0)
            digits = _digits_only(raw)
            if not 13 <= len(digits) <= 19:
                continue
            if not luhn_valid(digits):
                continue
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.97,
                    detector=self.name,
                    value=raw,
                )
            )
        return out


class JPMyNumberDetector:
    name = "jp_mynumber"
    entity_type = "JP_MYNUMBER"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in MYNUMBER_RE.finditer(text):
            raw = m.group(0)
            if not mynumber_check_valid(raw):
                continue
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.99,
                    detector=self.name,
                    value=raw,
                )
            )
        return out
