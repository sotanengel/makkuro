from __future__ import annotations

import json

from makkuro.cli import main


def _make_audit_file(tmp_path, events):
    p = tmp_path / "audit.jsonl"
    lines = [json.dumps(e) for e in events]
    p.write_text("\n".join(lines) + "\n")
    return p


def test_stats_basic(tmp_path, capsys):
    path = _make_audit_file(tmp_path, [
        {"event": "redact", "type": "EMAIL", "detector": "email", "score": 0.99},
        {"event": "redact", "type": "EMAIL", "detector": "email", "score": 0.99},
        {"event": "redact", "type": "JP_MOBILE", "detector": "jp_mobile", "score": 0.98},
        {"event": "rehydrate"},
    ])
    rc = main(["audit", "stats", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "total_events: 4" in out
    assert "redact: 3" in out
    assert "rehydrate: 1" in out
    assert "EMAIL: 2" in out
    assert "JP_MOBILE: 1" in out


def test_stats_empty_file(tmp_path, capsys):
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    rc = main(["audit", "stats", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "total_events: 0" in out


def test_stats_missing_file(tmp_path, capsys):
    rc = main(["audit", "stats", str(tmp_path / "missing.jsonl")])
    assert rc == 2


def test_stats_malformed_lines(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"event":"redact","type":"EMAIL"}\nnot json\n{"event":"rehydrate"}\n')
    rc = main(["audit", "stats", str(path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "total_events: 2" in out
