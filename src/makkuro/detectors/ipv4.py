"""IPv4 address detector.

Detects dotted-decimal IPv4 addresses (e.g. ``192.168.1.1``) while
rejecting loopback (127.x), link-local (169.254.x), and broadcast
(255.255.255.255) addresses that rarely represent PII. Each octet is
validated to be in 0-255.
"""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

# Four dotted decimal octets, bounded by non-digit/non-dot.
_IPV4_RE = re.compile(
    r"(?<![0-9.])"
    r"(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
    r"(?![0-9.])"
)

# Prefixes that are rarely PII.
_IGNORE_PREFIXES = ("127.", "169.254.", "0.")
_BROADCAST = "255.255.255.255"


class IPv4Detector:
    """Detect IPv4 addresses in text."""

    name = "ipv4"
    entity_type = "IPV4_ADDRESS"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in _IPV4_RE.finditer(text):
            raw = m.group(0)
            if raw == _BROADCAST:
                continue
            if any(raw.startswith(p) for p in _IGNORE_PREFIXES):
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
