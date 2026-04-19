"""Baseline regex detectors independent of locale."""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

EMAIL_RE = re.compile(
    r"(?<![\w.+-])"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}"
    r"(?![\w-])"
)


class EmailDetector:
    """RFC5322-subset email detector."""

    name = "email"
    entity_type = "EMAIL"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in EMAIL_RE.finditer(text):
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=0.99,
                    detector=self.name,
                    value=m.group(0),
                )
            )
        return out
