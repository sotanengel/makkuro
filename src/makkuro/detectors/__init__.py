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
from makkuro.detectors.secrets import make_secret_detectors

DEFAULT_DETECTORS: list[Detector] = [
    EmailDetector(),
    JPMobileDetector(),
    JPLandlineDetector(),
    JPZipDetector(),
    JPCreditCardDetector(),
    JPMyNumberDetector(),
    *make_secret_detectors(),
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
    "make_secret_detectors",
]
