"""Detector protocol and detection record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Detection:
    """A single detected span in a string.

    Offsets are measured in Python string index units (code points for ``str``),
    half-open: ``text[start:end]`` is the matched substring.
    """

    type: str
    start: int
    end: int
    score: float
    detector: str
    value: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid offsets: start={self.start} end={self.end}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0,1], got {self.score}")


@runtime_checkable
class Detector(Protocol):
    """Detector plugin contract."""

    name: str

    def scan(self, text: str) -> list[Detection]:
        """Return all detections found in ``text``."""
        ...
