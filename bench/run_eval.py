"""Run baseline detectors over a JSON sample file and print F1 metrics.

Usage:
    python -m bench.run_eval bench/data/toy/samples.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench.evaluator.metrics import SpanLike, evaluate
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.pipeline import run_detectors


def _locate(text: str, value: str, start_from: int) -> int:
    return text.find(value, start_from)


def _build_gold(text: str, entities: list[dict]) -> list[SpanLike]:
    cursor = 0
    gold: list[SpanLike] = []
    for ent in entities:
        idx = _locate(text, ent["value"], cursor)
        if idx < 0:
            raise ValueError(f"gold value not found in text: {ent['value']!r}")
        gold.append(SpanLike(type=ent["type"], start=idx, end=idx + len(ent["value"])))
        cursor = idx + len(ent["value"])
    return gold


def _predict(text: str) -> list[SpanLike]:
    detections = run_detectors(DEFAULT_DETECTORS, text)
    return [SpanLike(type=d.type, start=d.start, end=d.end) for d in detections]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", help="path to samples.json")
    parser.add_argument(
        "--mode",
        choices=["strict", "loose", "both"],
        default="both",
    )
    args = parser.parse_args(argv)

    samples = json.loads(Path(args.samples).read_text(encoding="utf-8"))
    predictions: list[list[SpanLike]] = []
    gold: list[list[SpanLike]] = []
    for s in samples:
        predictions.append(_predict(s["text"]))
        gold.append(_build_gold(s["text"], s["entities"]))

    modes = ["strict", "loose"] if args.mode == "both" else [args.mode]
    for mode in modes:
        report = evaluate(predictions, gold, mode=mode)  # type: ignore[arg-type]
        print(f"\n=== {mode.upper()} ===")
        print(f"{'type':<20} {'P':>6} {'R':>6} {'F1':>6}  tp/fp/fn")
        for t in sorted(report.per_type):
            s = report.per_type[t]
            print(
                f"{t:<20} {s.precision:>6.2f} {s.recall:>6.2f} {s.f1:>6.2f}  "
                f"{s.tp}/{s.fp}/{s.fn}"
            )
        print(f"macro_f1 = {report.macro_f1:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
