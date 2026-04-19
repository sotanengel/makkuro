"""IBAN (International Bank Account Number) detector.

Matches ISO 13616 formatted IBANs: 2-letter country code + 2 check
digits + up to 30 alphanumeric characters. Each candidate is validated
with the mod-97 checksum algorithm to minimize false positives.
"""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

# IBAN: 2 uppercase letters + 2 digits + 12-30 alphanumeric (with optional spaces/dashes).
_IBAN_RE = re.compile(
    r"(?<![A-Z0-9])"
    r"[A-Z]{2}\d{2}[\s-]?[A-Z0-9]{4}(?:[\s-]?[A-Z0-9]{4}){2,7}(?:[\s-]?[A-Z0-9]{1,4})?"
    r"(?![A-Z0-9])"
)

# ISO 3166-1 alpha-2 country codes that use IBAN.
_IBAN_COUNTRIES = frozenset({
    "AD", "AE", "AL", "AT", "AZ", "BA", "BE", "BG", "BH", "BR",
    "BY", "CH", "CR", "CY", "CZ", "DE", "DK", "DO", "EE", "EG",
    "ES", "FI", "FO", "FR", "GB", "GE", "GI", "GL", "GR", "GT",
    "HR", "HU", "IE", "IL", "IQ", "IS", "IT", "JO", "KW", "KZ",
    "LB", "LC", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
    "MR", "MT", "MU", "NL", "NO", "PK", "PL", "PS", "PT", "QA",
    "RO", "RS", "SA", "SC", "SE", "SI", "SK", "SM", "ST", "SV",
    "TL", "TN", "TR", "UA", "VA", "VG", "XK",
})


def _iban_mod97(iban: str) -> bool:
    """Validate an IBAN using the ISO 7064 mod-97-10 algorithm."""
    clean = iban.replace(" ", "").replace("-", "").upper()
    if len(clean) < 15 or len(clean) > 34:
        return False
    country = clean[:2]
    if country not in _IBAN_COUNTRIES:
        return False
    # Move first 4 chars to end, convert letters to digits (A=10..Z=35).
    rearranged = clean[4:] + clean[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch) - 55)
    return int(numeric) % 97 == 1


class IBANDetector:
    """Detect IBAN account numbers in text."""

    name = "iban"
    entity_type = "IBAN"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in _IBAN_RE.finditer(text):
            raw = m.group(0)
            if not _iban_mod97(raw):
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
