"""Strict and loose Precision / Recall / F1 metrics for PII detection.

* Strict: predicted span must have the same type AND the same (start,end).
* Loose:  predicted span must have the same type AND overlap >= 0.5 with gold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["strict", "loose"]


@dataclass
class SpanLike:
    type: str
    start: int
    end: int


@dataclass
class EntityScore:
    type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class EvalReport:
    mode: Mode
    per_type: dict[str, EntityScore] = field(default_factory=dict)

    @property
    def macro_f1(self) -> float:
        if not self.per_type:
            return 0.0
        return sum(s.f1 for s in self.per_type.values()) / len(self.per_type)


def _overlap_ratio(a: SpanLike, b: SpanLike) -> float:
    inter = max(0, min(a.end, b.end) - max(a.start, b.start))
    if inter == 0:
        return 0.0
    union = max(a.end, b.end) - min(a.start, b.start)
    return inter / union if union else 0.0


def _match(pred: SpanLike, gold: SpanLike, mode: Mode) -> bool:
    if pred.type != gold.type:
        return False
    if mode == "strict":
        return pred.start == gold.start and pred.end == gold.end
    return _overlap_ratio(pred, gold) >= 0.5


def evaluate(
    predictions: list[list[SpanLike]],
    gold: list[list[SpanLike]],
    mode: Mode = "strict",
) -> EvalReport:
    """Compute per-type scores over a parallel list of predictions and gold."""
    if len(predictions) != len(gold):
        raise ValueError("predictions and gold must have equal length")
    scores: dict[str, EntityScore] = {}
    for preds, golds in zip(predictions, gold, strict=False):
        matched_pred: set[int] = set()
        matched_gold: set[int] = set()
        for gi, g in enumerate(golds):
            for pi, p in enumerate(preds):
                if pi in matched_pred:
                    continue
                if _match(p, g, mode):
                    matched_pred.add(pi)
                    matched_gold.add(gi)
                    scores.setdefault(g.type, EntityScore(type=g.type)).tp += 1
                    break
        for gi, g in enumerate(golds):
            if gi not in matched_gold:
                scores.setdefault(g.type, EntityScore(type=g.type)).fn += 1
        for pi, p in enumerate(preds):
            if pi not in matched_pred:
                scores.setdefault(p.type, EntityScore(type=p.type)).fp += 1
    return EvalReport(mode=mode, per_type=scores)
