"""Tests for the age-encrypted persistent vault.

Skipped when ``pyrage`` isn't installed; the unit tests then serve as
executable documentation of the intended behaviour.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("pyrage")

from makkuro.vault.age import AgeVault, AgeVaultError  # noqa: E402


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "data" / "vault.age", tmp_path / "config" / "identity.txt"


def test_create_generates_identity_and_empty_vault(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    v = AgeVault.create(vault_path, identity_path)
    assert vault_path.exists()
    assert identity_path.exists()
    assert len(v) == 0
    # Identity file must be 0600 on posix.
    if os.name == "posix":
        assert (os.stat(identity_path).st_mode & 0o777) == 0o600
        assert (os.stat(vault_path).st_mode & 0o777) == 0o600


def test_round_trip_put_save_reopen(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    v = AgeVault.create(vault_path, identity_path)
    v.put("<MAKKURO_EMAIL_cafef00d>", "alice@example.com")
    v.put("<MAKKURO_JP_MOBILE_12345678>", "090-1234-5678")
    v.save()

    identity = AgeVault.load_identity(identity_path)
    v2 = AgeVault.open(vault_path, identity)
    assert len(v2) == 2
    assert v2.get("<MAKKURO_EMAIL_cafef00d>") == "alice@example.com"
    assert "<MAKKURO_JP_MOBILE_12345678>" in v2


def test_create_refuses_overwrite(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    AgeVault.create(vault_path, identity_path)
    with pytest.raises(AgeVaultError):
        AgeVault.create(vault_path, identity_path)


def test_open_with_wrong_identity_fails(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    v = AgeVault.create(vault_path, identity_path)
    v.put("<MAKKURO_EMAIL_aa>", "x@y.jp")
    v.save()

    # Swap in a different identity.
    import pyrage

    other = pyrage.x25519.Identity.generate()
    with pytest.raises(AgeVaultError):
        AgeVault.open(vault_path, other)


def test_identity_perms_enforced(tmp_path: Path):
    if os.name != "posix":
        pytest.skip("posix-only perms check")
    _, identity_path = _paths(tmp_path)
    vault_path = tmp_path / "data" / "vault.age"
    v = AgeVault.create(vault_path, identity_path)
    v.save()
    # Loosen perms and re-open: must be rejected.
    os.chmod(identity_path, 0o644)
    with pytest.raises(AgeVaultError):
        AgeVault.load_identity(identity_path)


def test_purge_all_clears_contents(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    v = AgeVault.create(vault_path, identity_path)
    v.put("<MAKKURO_EMAIL_aaaa>", "a@b.jp")
    v.put("<MAKKURO_EMAIL_bbbb>", "c@d.jp")
    v.save()

    v.purge_all()
    assert len(v) == 0

    identity = AgeVault.load_identity(identity_path)
    reloaded = AgeVault.open(vault_path, identity)
    assert len(reloaded) == 0


def test_atomic_write_leaves_no_tmp_files(tmp_path: Path):
    vault_path, identity_path = _paths(tmp_path)
    v = AgeVault.create(vault_path, identity_path)
    v.put("<MAKKURO_EMAIL_abc>", "x@y.jp")
    v.save()
    leftovers = list(vault_path.parent.glob(".makkuro-vault-*.tmp"))
    assert leftovers == []
