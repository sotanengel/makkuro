"""Detection aggregation pipeline.

Runs a chain of detectors against a single string and resolves overlaps
deterministically: longer span wins, score breaks ties, earlier start
breaks further ties.
"""

from __future__ import annotations

from collections.abc import Iterable

from makkuro.detectors.base import Detection, Detector


def run_detectors(detectors: Iterable[Detector], text: str) -> list[Detection]:
    """Run each detector and return non-overlapping detections."""
    found: list[Detection] = []
    for det in detectors:
        found.extend(det.scan(text))
    return _resolve_overlaps(found)


def _resolve_overlaps(detections: list[Detection]) -> list[Detection]:
    if not detections:
        return []
    # Longer span wins over shorter, score breaks ties, earlier start next.
    # The length-first rule prevents a narrow high-score match (e.g. a ZIP-like
    # 3+4 digit subpattern) from displacing a broader landline or mobile match
    # that contains it.
    detections.sort(key=lambda d: (-(d.end - d.start), -d.score, d.start))
    chosen: list[Detection] = []
    for d in detections:
        if any(_overlaps(d, c) for c in chosen):
            continue
        chosen.append(d)
    chosen.sort(key=lambda d: d.start)
    return chosen


def _overlaps(a: Detection, b: Detection) -> bool:
    return a.start < b.end and b.start < a.end
