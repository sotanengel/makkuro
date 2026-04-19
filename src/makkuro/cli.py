"""makkuro CLI (Phase 0 skeleton).

Only ``version``, ``test``, and ``doctor`` are implemented at this stage.
Proxy subcommands land in Phase 1.
"""

from __future__ import annotations

import argparse
import json
import sys

from makkuro import __version__
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.pipeline import run_detectors
from makkuro.placeholder import PlaceholderMint, substitute


def _cmd_version(_: argparse.Namespace) -> int:
    print(f"makkuro {__version__}")
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    text = args.text
    detections = run_detectors(DEFAULT_DETECTORS, text)
    mint = PlaceholderMint()
    redacted = substitute(text, detections, mint)
    report = {
        "input": text,
        "redacted": redacted,
        "detections": [
            {
                "type": d.type,
                "start": d.start,
                "end": d.end,
                "score": d.score,
                "detector": d.detector,
                "value": d.value,
            }
            for d in detections
        ],
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    print(f"makkuro {__version__}")
    print(f"python {sys.version.split()[0]}")
    print(f"detectors: {len(DEFAULT_DETECTORS)} enabled")
    for d in DEFAULT_DETECTORS:
        print(f"  - {d.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="makkuro", description="Local redaction proxy for AI CLIs.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ver = sub.add_parser("version", help="print version and exit")
    p_ver.set_defaults(func=_cmd_version)

    p_test = sub.add_parser("test", help="dry-run detectors on a single string")
    p_test.add_argument("text", help="text to scan")
    p_test.set_defaults(func=_cmd_test)

    p_doc = sub.add_parser("doctor", help="report loaded detectors and environment")
    p_doc.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
