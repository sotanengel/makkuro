from __future__ import annotations

from pathlib import Path

from bench.run_eval import main


def test_toy_benchmark_runs(capsys):
    path = Path(__file__).resolve().parents[1] / "bench" / "data" / "toy" / "samples.json"
    rc = main([str(path), "--mode", "both"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "STRICT" in out
    assert "LOOSE" in out
    assert "macro_f1" in out
