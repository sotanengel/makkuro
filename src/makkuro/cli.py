"""makkuro CLI.

Phase 0: ``version``, ``test``, ``doctor``.
Phase 1 adds ``start`` (run proxy), ``status`` (query /v1/status of a running
proxy), and ``install`` (emit shell env snippet for supported AI CLIs).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from makkuro import __version__
from makkuro.config import load as load_config
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.pipeline import run_detectors
from makkuro.placeholder import PlaceholderMint, substitute

_INSTALL_SNIPPETS: dict[str, str] = {
    "claude": "export ANTHROPIC_BASE_URL=http://127.0.0.1:{port}",
    "codex": "export OPENAI_BASE_URL=http://127.0.0.1:{port}",
    "gemini": "export GOOGLE_API_BASE=http://127.0.0.1:{port}",
    "aider": '# add to your aider command:\n#   aider --openai-api-base http://127.0.0.1:{port}',
}


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


def _cmd_start(args: argparse.Namespace) -> int:
    # Imported lazily so that ``makkuro version`` never pulls in starlette /
    # uvicorn / httpx -- keeps cold-start fast and lets uvicorn be an optional
    # runtime dep in constrained environments.
    from makkuro.proxy.server import run

    cfg_path = Path(args.config) if args.config else None
    cfg = load_config(cfg_path)
    if args.port:
        cfg.proxy.port = args.port
    if args.bind:
        cfg.proxy.bind = args.bind
    run(cfg)
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    tool = args.tool
    snippet = _INSTALL_SNIPPETS.get(tool)
    if snippet is None:
        print(f"unknown tool: {tool}", file=sys.stderr)
        return 2
    print(snippet.format(port=args.port))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="makkuro",
        description="Local redaction proxy for AI CLIs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ver = sub.add_parser("version", help="print version and exit")
    p_ver.set_defaults(func=_cmd_version)

    p_test = sub.add_parser("test", help="dry-run detectors on a single string")
    p_test.add_argument("text", help="text to scan")
    p_test.set_defaults(func=_cmd_test)

    p_doc = sub.add_parser("doctor", help="report loaded detectors and environment")
    p_doc.set_defaults(func=_cmd_doctor)

    p_start = sub.add_parser("start", help="start the proxy in the foreground")
    p_start.add_argument("--config", help="path to a TOML config file")
    p_start.add_argument("--port", type=int, help="override proxy port")
    p_start.add_argument("--bind", help="override bind address")
    p_start.set_defaults(func=_cmd_start)

    p_ins = sub.add_parser("install", help="emit an env snippet for a supported CLI")
    p_ins.add_argument("tool", choices=sorted(_INSTALL_SNIPPETS))
    p_ins.add_argument("--port", type=int, default=8787)
    p_ins.set_defaults(func=_cmd_install)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
