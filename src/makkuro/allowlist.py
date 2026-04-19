"""Detection suppression based on an allow list.

A detection is dropped if any of the following match its raw text:

* an explicit ``emails`` entry (case-insensitive exact match);
* a registered domain — the ``@`` host part of an EMAIL detection;
* a regex from ``patterns`` (``re.search`` on the whole detection text).

Allow-list rules apply *after* detection so the detector decides what's a
secret, but the operator gets to whitelist known-safe values
(documentation samples, test fixtures, public corporate emails, …).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from makkuro.detectors.base import Detection


@dataclass
class AllowList:
    emails: frozenset[str] = field(default_factory=frozenset)
    domains: frozenset[str] = field(default_factory=frozenset)
    patterns: tuple[re.Pattern[str], ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AllowList:
        emails = frozenset(
            str(e).lower() for e in (data.get("emails") or []) if isinstance(e, str)
        )
        domains = frozenset(
            str(d).lower() for d in (data.get("domains") or []) if isinstance(d, str)
        )
        raw_patterns = data.get("patterns") or []
        if not isinstance(raw_patterns, list):
            raise ValueError("allow_list.patterns must be a list of regex strings")
        compiled: list[re.Pattern[str]] = []
        for p in raw_patterns:
            if not isinstance(p, str):
                continue
            try:
                compiled.append(re.compile(p))
            except re.error as e:
                raise ValueError(f"allow_list pattern {p!r} did not compile: {e}") from e
        return cls(emails=emails, domains=domains, patterns=tuple(compiled))

    def is_empty(self) -> bool:
        return not (self.emails or self.domains or self.patterns)

    def allows(self, det: Detection) -> bool:
        """True if ``det`` matches any allow-list entry and should be dropped."""
        if self.is_empty():
            return False
        value = det.value
        lower = value.lower()
        if det.type == "EMAIL":
            if lower in self.emails:
                return True
            host = lower.rsplit("@", 1)[-1] if "@" in lower else ""
            if host and host in self.domains:
                return True
        for pat in self.patterns:
            if pat.search(value):
                return True
        return False

    def filter(self, detections: list[Detection]) -> list[Detection]:
        if self.is_empty():
            return detections
        return [d for d in detections if not self.allows(d)]
