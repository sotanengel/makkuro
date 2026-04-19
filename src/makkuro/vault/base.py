"""Vault protocol.

A ``Vault`` stores the bidirectional mapping between placeholders and the
original secrets they represent. Phase 1 ships only an in-memory backend;
`age` and OS-keychain backends land in Phase 2.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Vault(Protocol):
    def put(self, placeholder: str, original: str) -> None: ...
    def get(self, placeholder: str) -> str | None: ...
    def __contains__(self, placeholder: str) -> bool: ...
    def __len__(self) -> int: ...
