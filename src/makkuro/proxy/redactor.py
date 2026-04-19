"""Request / response redaction wired to the detector chain and a vault.

The canonical form's text leaves are run through :func:`run_detectors`; each
detection is minted into a placeholder and recorded in the vault so the
response path (when enabled) can restore the originals.
"""

from __future__ import annotations

from dataclasses import dataclass

from makkuro.allowlist import AllowList
from makkuro.audit import AuditEvent, AuditWriter
from makkuro.detectors import DEFAULT_DETECTORS
from makkuro.detectors.base import Detector
from makkuro.pipeline import run_detectors
from makkuro.placeholder import PlaceholderMint, rehydrate, substitute
from makkuro.protocol.base import CanonicalRequest
from makkuro.vault.base import Vault


@dataclass
class RedactionStats:
    detections: int = 0
    rehydrated: int = 0
    unknown_placeholders: int = 0


class Redactor:
    """Applies detector chain + placeholder minting + vault bookkeeping."""

    def __init__(
        self,
        vault: Vault,
        detectors: list[Detector] | None = None,
        mint: PlaceholderMint | None = None,
        audit: AuditWriter | None = None,
        allow_list: AllowList | None = None,
    ) -> None:
        self.vault = vault
        self.detectors = detectors if detectors is not None else list(DEFAULT_DETECTORS)
        self.mint = mint if mint is not None else PlaceholderMint()
        self.audit = audit
        self.allow_list = allow_list if allow_list is not None else AllowList()
        self.stats = RedactionStats()
        self._request_id: str = ""

    def bind_request(self, request_id: str) -> None:
        """Associate subsequent audit events with this request ID."""
        self._request_id = request_id

    # ---- request path ----

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        detections = run_detectors(self.detectors, text)
        detections = self.allow_list.filter(detections)
        if not detections:
            return text
        redacted = substitute(text, detections, self.mint)
        for det in detections:
            original = text[det.start:det.end]
            placeholder = self.mint.mint(det.type, original)
            self.vault.put(placeholder, original)
            self.stats.detections += 1
            if self.audit is not None:
                self.audit.write(
                    AuditEvent(
                        event="redact",
                        placeholder=placeholder,
                        type=det.type,
                        detector=det.detector,
                        score=det.score,
                        request_id=self._request_id,
                    )
                )
        return redacted

    def redact_request(self, canonical: CanonicalRequest) -> CanonicalRequest:
        if canonical.system is not None:
            canonical.system = self.redact_text(canonical.system)
        for msg in canonical.messages:
            for block in msg.content_blocks:
                if block.type == "text" and block.text is not None:
                    block.text = self.redact_text(block.text)
                elif block.type == "tool_use" and block.tool_input is not None:
                    block.tool_input = self._redact_json(block.tool_input)
                elif block.type == "tool_result":
                    block.tool_output = self._redact_json(block.tool_output)
        return canonical

    # ---- MCP deep-redact ----

    # JSON-RPC control fields that are always pass-through; never descend into
    # them so a tool name, id, or method with secret-looking entropy stays put.
    _CONTROL_KEYS = frozenset({"jsonrpc", "id", "method", "tool_use_id"})

    def _redact_json(self, value: object) -> object:
        """Recursively redact string leaves of an arbitrary JSON payload.

        Control fields in :attr:`_CONTROL_KEYS` are left untouched so the
        protocol stays legal.
        """
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, list):
            return [self._redact_json(v) for v in value]
        if isinstance(value, dict):
            out: dict[str, object] = {}
            for k, v in value.items():
                if k in self._CONTROL_KEYS:
                    out[k] = v
                else:
                    out[k] = self._redact_json(v)
            return out
        return value

    # ---- response path ----

    def rehydrate_text(self, text: str) -> str:
        restored, unknown = rehydrate(text, self.mint)
        if restored != text:
            self.stats.rehydrated += 1
            if self.audit is not None:
                self.audit.write(
                    AuditEvent(event="rehydrate", request_id=self._request_id)
                )
        if unknown:
            self.stats.unknown_placeholders += len(unknown)
            if self.audit is not None:
                for ph in unknown:
                    self.audit.write(
                        AuditEvent(
                            event="unknown_placeholder",
                            placeholder=ph,
                            request_id=self._request_id,
                        )
                    )
        # Only placeholders we actually minted come from the vault; the mint
        # already knows them, so no extra vault lookup is needed here.
        return restored
