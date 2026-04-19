"""Placeholder substitution helpers.

Placeholders have the form ``<MAKKURO_{TYPE}_{8hex}>`` where the 8-hex tail is
the first 4 bytes of a blake2s digest of the raw value with an in-process
secret salt. Same (salt, value) -> same placeholder within the process.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field

from makkuro.detectors.base import Detection

_PLACEHOLDER_RE = re.compile(r"<MAKKURO_(?P<type>[A-Z0-9_]+)_(?P<hash>[0-9a-f]{8})>")


def _make_salt() -> bytes:
    return os.urandom(16)


@dataclass
class PlaceholderMint:
    """Minter that keeps value->placeholder and placeholder->value maps.

    One instance per proxy process. ``salt`` is randomized on init so hashes
    are not portable across processes.
    """

    salt: bytes = field(default_factory=_make_salt)
    _by_value: dict[tuple[str, str], str] = field(default_factory=dict)
    _by_placeholder: dict[str, str] = field(default_factory=dict)

    def mint(self, entity_type: str, value: str) -> str:
        key = (entity_type, value)
        hit = self._by_value.get(key)
        if hit is not None:
            return hit
        digest = hashlib.blake2s(
            value.encode("utf-8"),
            digest_size=4,
            key=self.salt,
        ).hexdigest()
        placeholder = f"<MAKKURO_{entity_type}_{digest}>"
        self._by_value[key] = placeholder
        self._by_placeholder[placeholder] = value
        return placeholder

    def resolve(self, placeholder: str) -> str | None:
        return self._by_placeholder.get(placeholder)

    def __len__(self) -> int:
        return len(self._by_placeholder)


def substitute(text: str, detections: list[Detection], mint: PlaceholderMint) -> str:
    """Replace detection spans with placeholders, back-to-front."""
    if not detections:
        return text
    ordered = sorted(detections, key=lambda d: d.start)
    out: list[str] = []
    cursor = 0
    for d in ordered:
        if d.start < cursor:
            # Overlap that shouldn't happen if pipeline resolved overlaps.
            continue
        out.append(text[cursor:d.start])
        out.append(mint.mint(d.type, text[d.start:d.end]))
        cursor = d.end
    out.append(text[cursor:])
    return "".join(out)


def rehydrate(text: str, mint: PlaceholderMint) -> tuple[str, list[str]]:
    """Replace placeholders with their original values.

    Returns (rehydrated_text, unknown_placeholders). A placeholder that has no
    mapping is left intact and reported in ``unknown_placeholders``.
    """
    unknown: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        ph = m.group(0)
        original = mint.resolve(ph)
        if original is None:
            unknown.append(ph)
            return ph
        return original

    return _PLACEHOLDER_RE.sub(_sub, text), unknown
