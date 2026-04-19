"""User-defined regex detectors loaded from ``redaction.custom_patterns``.

Each entry is ``name = "regex string"``. The detector ``name`` becomes the
detector identifier, the ``entity_type`` is its uppercased form, and the
score defaults to 0.95. Patterns are compiled eagerly so a typo fails at
config load time, not on first request.
"""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection


class CustomPatternDetector:
    """A single user-defined regex detector."""

    def __init__(
        self,
        name: str,
        pattern: str,
        score: float = 0.95,
    ) -> None:
        if not name or not name.replace("_", "").isalnum():
            raise ValueError(
                f"custom pattern name {name!r} must be alphanumeric (underscores allowed)"
            )
        try:
            self._re = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"custom pattern {name!r} did not compile: {e}") from e
        self.name = name
        self.entity_type = name.upper()
        self._score = score

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in self._re.finditer(text):
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=self._score,
                    detector=self.name,
                    value=m.group(0),
                )
            )
        return out


def make_custom_detectors(patterns: dict[str, str]) -> list[CustomPatternDetector]:
    return [CustomPatternDetector(name=k, pattern=v) for k, v in patterns.items()]
