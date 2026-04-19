"""Placeholder <-> original value vault backends."""

from makkuro.vault.base import Vault
from makkuro.vault.memory import MemoryVault

# The age backend is optional: importing ``pyrage`` would pull in a native
# dependency that's not needed when users run with the memory vault. Guard
# the import so a plain ``from makkuro.vault import MemoryVault`` keeps
# working on systems without pyrage.
try:  # pragma: no cover - exercised via tests that mock / install pyrage
    from makkuro.vault.age import AgeVault, AgeVaultError
except ImportError:  # pragma: no cover
    AgeVault = None  # type: ignore[assignment]
    AgeVaultError = None  # type: ignore[assignment]

__all__ = ["AgeVault", "AgeVaultError", "MemoryVault", "Vault"]
