from __future__ import annotations

from makkuro.vault import MemoryVault


def test_memory_vault_put_get():
    v = MemoryVault()
    v.put("<MAKKURO_EMAIL_abcd1234>", "foo@example.com")
    assert v.get("<MAKKURO_EMAIL_abcd1234>") == "foo@example.com"


def test_memory_vault_contains_len():
    v = MemoryVault()
    assert len(v) == 0
    v.put("a", "1")
    assert "a" in v
    assert "b" not in v
    assert len(v) == 1


def test_memory_vault_get_missing():
    v = MemoryVault()
    assert v.get("missing") is None


def test_memory_vault_clear():
    v = MemoryVault()
    v.put("a", "1")
    v.put("b", "2")
    v.clear()
    assert len(v) == 0
