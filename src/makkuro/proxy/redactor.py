"""Request / response redaction wired to the detector chain and a vault.

The canonical form's text leaves are run through :func:`run_detectors`; each
detection is minted into a placeholder and recorded in the vault so the
response path (when enabled) can restore the originals.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    ) -> None:
        self.vault = vault
        self.detectors = detectors if detectors is not None else list(DEFAULT_DETECTORS)
        self.mint = mint if mint is not None else PlaceholderMint()
        self.stats = RedactionStats()

    # ---- request path ----

    def redact_text(self, text: str) -> str:
        if not text:
            return text
        detections = run_detectors(self.detectors, text)
        if not detections:
            return text
        redacted = substitute(text, detections, self.mint)
        for det in detections:
            original = text[det.start:det.end]
            placeholder = self.mint.mint(det.type, original)
            self.vault.put(placeholder, original)
            self.stats.detections += 1
        return redacted

    def redact_request(self, canonical: CanonicalRequest) -> CanonicalRequest:
        if canonical.system is not None:
            canonical.system = self.redact_text(canonical.system)
        for msg in canonical.messages:
            for block in msg.content_blocks:
                if block.type == "text" and block.text is not None:
                    block.text = self.redact_text(block.text)
        return canonical

    # ---- response path ----

    def rehydrate_text(self, text: str) -> str:
        restored, unknown = rehydrate(text, self.mint)
        if restored != text:
            self.stats.rehydrated += 1
        if unknown:
            self.stats.unknown_placeholders += len(unknown)
        # Only placeholders we actually minted come from the vault; the mint
        # already knows them, so no extra vault lookup is needed here.
        return restored
