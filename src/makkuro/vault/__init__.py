"""Placeholder <-> original value vault backends."""

from makkuro.vault.base import Vault
from makkuro.vault.memory import MemoryVault

__all__ = ["MemoryVault", "Vault"]
