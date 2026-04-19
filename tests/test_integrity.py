from __future__ import annotations

from pathlib import Path

from makkuro.integrity import (
    _MANIFEST_REL_PATH,
    generate_manifest,
    load_manifest,
    verify,
)


def _write_manifest(root: Path, files: dict[str, str]) -> None:
    dir_ = root / _MANIFEST_REL_PATH.parent
    dir_.mkdir(parents=True, exist_ok=True)
    lines = ["[files]"]
    for rel, digest in sorted(files.items()):
        lines.append(f'"{rel}" = "{digest}"')
    (root / _MANIFEST_REL_PATH).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_dev_install_has_no_manifest():
    # The shipped package tree in this test run has no manifest; `verify`
    # must report that without crashing so dev installs can opt in.
    report = verify()
    assert not report.manifest_present


def test_round_trip_on_temp_tree(tmp_path: Path):
    root = tmp_path
    (root / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (root / "mod.py").write_text("y = 2\n", encoding="utf-8")
    manifest = generate_manifest(root)
    assert set(manifest) == {"__init__.py", "mod.py"}
    _write_manifest(root, manifest)
    loaded = load_manifest(root)
    assert loaded == manifest
    report = verify(root)
    assert report.ok
    assert report.checked == 2


def test_modified_file_flagged(tmp_path: Path):
    root = tmp_path
    (root / "x.py").write_text("a = 1\n", encoding="utf-8")
    manifest = generate_manifest(root)
    _write_manifest(root, manifest)
    # Mutate the installed copy.
    (root / "x.py").write_text("a = 999\n", encoding="utf-8")
    report = verify(root)
    assert not report.ok
    assert "x.py" in report.modified


def test_unexpected_file_flagged(tmp_path: Path):
    root = tmp_path
    (root / "a.py").write_text("a = 1\n", encoding="utf-8")
    _write_manifest(root, generate_manifest(root))
    # An attacker drops an extra .py into the package tree.
    (root / "evil.py").write_text("import os\n", encoding="utf-8")
    report = verify(root)
    assert not report.ok
    assert "evil.py" in report.unexpected


def test_missing_file_flagged(tmp_path: Path):
    root = tmp_path
    (root / "a.py").write_text("a = 1\n", encoding="utf-8")
    (root / "b.py").write_text("b = 2\n", encoding="utf-8")
    _write_manifest(root, generate_manifest(root))
    (root / "b.py").unlink()
    report = verify(root)
    assert not report.ok
    assert "b.py" in report.missing
