from __future__ import annotations

import json

from makkuro.cli import main


def test_version(capsys):
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("makkuro ")


def test_test_subcommand_redacts(capsys):
    rc = main(["test", "連絡先 foo@example.com まで"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["redacted"] != payload["input"]
    assert any(d["type"] == "EMAIL" for d in payload["detections"])


def test_doctor(capsys):
    rc = main(["doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "detectors:" in out
