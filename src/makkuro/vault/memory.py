"""In-memory vault.

Non-persistent; contents are lost when the proxy process exits. Suitable for
dev and tests. Phase 2 will add ``age``-backed persistence.
"""

from __future__ import annotations


class MemoryVault:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def put(self, placeholder: str, original: str) -> None:
        self._store[placeholder] = original

    def get(self, placeholder: str) -> str | None:
        return self._store.get(placeholder)

    def __contains__(self, placeholder: str) -> bool:
        return placeholder in self._store

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
