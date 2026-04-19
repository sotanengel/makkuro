"""Canonical message form shared across provider adapters.

Each adapter round-trips its provider-specific JSON schema into this
representation so the redaction pipeline operates on a single structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ContentBlock:
    """One fragment of a message.

    * ``text``       plain text turn.
    * ``tool_use``   the model asking for a tool call (JSON arguments in
                     ``tool_input``).
    * ``tool_result`` the tool's reply (arbitrary payload in ``tool_output``).
    * ``image``      opaque image reference, left untouched.
    """

    type: str
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: Any | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalMessage:
    role: str  # user | assistant | system | tool
    content_blocks: list[ContentBlock] = field(default_factory=list)


@dataclass
class CanonicalRequest:
    system: str | None
    messages: list[CanonicalMessage]
    extra: dict[str, Any] = field(default_factory=dict)


class ProtocolAdapter(Protocol):
    """Adapter between provider-native JSON and the canonical form."""

    name: str
    upstream_path_prefixes: tuple[str, ...]

    def decode_request(self, body: dict[str, Any]) -> CanonicalRequest: ...

    def encode_request(
        self,
        canonical: CanonicalRequest,
        original: dict[str, Any],
    ) -> dict[str, Any]: ...

    def extract_response_text(
        self,
        body: dict[str, Any],
    ) -> list[tuple[list[str | int], str]]: ...

    def apply_response_text(
        self,
        body: dict[str, Any],
        edits: list[tuple[list[str | int], str]],
    ) -> dict[str, Any]: ...
