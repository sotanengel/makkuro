"""makkuro CLI.

Subcommands so far:

* ``version`` — print version.
* ``test`` — dry-run detectors on a single string.
* ``doctor`` — environment and detector summary.
* ``start`` — run the proxy in the foreground.
* ``install`` — emit an env snippet for a supported CLI.
* ``policy validate`` — validate a TOML config file against the bundled schema.
* ``audit tail`` — print the last N audit events.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from makkuro import __version__
from makkuro.config import load as load_config
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.integrity import verify as verify_integrity
from makkuro.pipeline import run_detectors
from makkuro.placeholder import PlaceholderMint, substitute
from makkuro.policy import validate as validate_policy

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


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)
    print(f"makkuro {__version__}")
    print(f"python {sys.version.split()[0]}")
    print(f"bind: {cfg.proxy.bind}:{cfg.proxy.port}")
    print(f"mode: {cfg.redaction.mode}  rehydrate: {cfg.redaction.rehydrate}")
    print(f"upstream_hosts: {sorted(cfg.upstream_hosts)}")
    print(f"audit: {'on' if cfg.audit.enabled else 'off'}  path: {cfg.audit.path or '-'}")
    print(f"detectors: {len(DEFAULT_DETECTORS)} enabled")
    for d in DEFAULT_DETECTORS:
        print(f"  - {d.name}")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
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


def _cmd_policy_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"config file not found: {path}", file=sys.stderr)
        return 2
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        print(f"invalid TOML: {e}", file=sys.stderr)
        return 1
    report = validate_policy(data)
    if report.ok:
        print(f"OK: {path}")
        return 0
    for err in report.errors:
        print(f"  {err}", file=sys.stderr)
    print(f"{len(report.errors)} error(s) in {path}", file=sys.stderr)
    return 1


def _cmd_verify(_: argparse.Namespace) -> int:
    report = verify_integrity()
    print(report.summary())
    if report.modified:
        for rel in report.modified:
            print(f"  modified: {rel}", file=sys.stderr)
    if report.missing:
        for rel in report.missing:
            print(f"  missing:  {rel}", file=sys.stderr)
    if report.unexpected:
        for rel in report.unexpected:
            print(f"  extra:    {rel}", file=sys.stderr)
    return 0 if report.ok else 1


def _cmd_audit_tail(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"audit file not found: {path}", file=sys.stderr)
        return 2
    with path.open("r", encoding="utf-8") as h:
        lines = h.readlines()
    for line in lines[-args.n:]:
        sys.stdout.write(line)
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
    p_doc.add_argument("--config", help="path to a TOML config file")
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

    p_ver_cmd = sub.add_parser("verify", help="self-integrity check (SC-7)")
    p_ver_cmd.set_defaults(func=_cmd_verify)

    p_pol = sub.add_parser("policy", help="policy tools")
    pol_sub = p_pol.add_subparsers(dest="policy_command", required=True)
    p_pol_val = pol_sub.add_parser(
        "validate", help="validate a TOML config against the bundled schema"
    )
    p_pol_val.add_argument("path", help="path to the config file")
    p_pol_val.set_defaults(func=_cmd_policy_validate)

    p_aud = sub.add_parser("audit", help="audit log tools")
    aud_sub = p_aud.add_subparsers(dest="audit_command", required=True)
    p_aud_tail = aud_sub.add_parser("tail", help="print the last N audit events")
    p_aud_tail.add_argument("path", help="path to the JSONL audit file")
    p_aud_tail.add_argument("-n", type=int, default=20, help="number of lines")
    p_aud_tail.set_defaults(func=_cmd_audit_tail)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
