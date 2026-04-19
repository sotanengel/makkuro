"""Detector plugins for makkuro."""

from makkuro.detectors.base import Detection, Detector
from makkuro.detectors.jp_pii import (
    JPCreditCardDetector,
    JPLandlineDetector,
    JPMobileDetector,
    JPMyNumberDetector,
    JPZipDetector,
)
from makkuro.detectors.regex_base import EmailDetector

DEFAULT_DETECTORS: list[Detector] = [
    EmailDetector(),
    JPMobileDetector(),
    JPLandlineDetector(),
    JPZipDetector(),
    JPCreditCardDetector(),
    JPMyNumberDetector(),
]

__all__ = [
    "DEFAULT_DETECTORS",
    "Detection",
    "Detector",
    "EmailDetector",
    "JPCreditCardDetector",
    "JPLandlineDetector",
    "JPMobileDetector",
    "JPMyNumberDetector",
    "JPZipDetector",
]
