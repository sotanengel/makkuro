from __future__ import annotations

import json
from pathlib import Path

from makkuro.audit import AuditEvent, AuditWriter


def test_memory_writer_records_events(tmp_path: Path):
    w = AuditWriter(path=None, enabled=True)
    w.write(AuditEvent(event="redact", placeholder="<p>", type="EMAIL"))
    events = w.buffered()
    assert len(events) == 1
    assert events[0]["event"] == "redact"
    assert events[0]["placeholder"] == "<p>"
    assert "ts" in events[0]


def test_file_writer_appends_jsonl(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    w = AuditWriter(path=path, enabled=True)
    w.write(AuditEvent(event="redact", placeholder="<p1>", type="EMAIL"))
    w.write(AuditEvent(event="rehydrate", request_id="r1"))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "redact"
    assert first["placeholder"] == "<p1>"
    second = json.loads(lines[1])
    assert second["event"] == "rehydrate"
    assert second["request_id"] == "r1"


def test_disabled_writer_is_noop(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    w = AuditWriter(path=path, enabled=False)
    w.write(AuditEvent(event="redact", placeholder="<p>"))
    assert not path.exists() or path.read_text() == ""
    assert w.buffered() == []


def test_audit_never_contains_plaintext(tmp_path: Path):
    # Invariant check: an AuditEvent struct has no field for the original secret,
    # so no code path in makkuro can write plaintext through AuditWriter.
    fields = AuditEvent.__dataclass_fields__.keys()
    assert "original" not in fields
    assert "value" not in fields
    assert "plaintext" not in fields
