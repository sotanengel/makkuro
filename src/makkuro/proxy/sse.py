"""SSE rehydration utilities.

The rehydrate path is trickier than the redact path because a placeholder
string like ``<MAKKURO_EMAIL_deadbeef>`` can straddle two SSE chunks. This
module provides a streaming buffer that holds back up to a look-back
window of bytes and only emits text once we're confident the tail of the
buffer can't complete a placeholder.

Decisions:

* Placeholder matches must be fully enclosed (``<MAKKURO_..._hex8>``).
* A buffer that ends in a partial ``<MAKKURO_...`` prefix is held until
  either a later chunk closes the placeholder or ``flush()`` is called.
* Unknown placeholders (not in the mint map) are passed through verbatim
  rather than rewritten — mirroring the batch path's behaviour.
"""

from __future__ import annotations

import re

from makkuro.placeholder import PlaceholderMint

_FULL_RE = re.compile(r"<MAKKURO_[A-Z0-9_]+_[0-9a-f]{8}>")

# Anything that could be a partial placeholder prefix. We only need to hold
# back suffixes that look like they could still become a full placeholder.
_PARTIAL_RE = re.compile(r"<(?:M(?:A(?:K(?:K(?:U(?:R(?:O(?:_[A-Z0-9a-f_]*)?)?)?)?)?)?)?)?$")


class SSERehydrator:
    """Rehydrates placeholders across an SSE (or chunked) text stream.

    Typical use:

        r = SSERehydrator(mint)
        for chunk in incoming:
            yield r.feed(chunk)
        yield r.flush()

    ``feed`` may return an empty string if the entire chunk had to be held
    back; callers should not assume chunk boundaries are preserved.
    """

    def __init__(self, mint: PlaceholderMint) -> None:
        self._mint = mint
        self._buf: str = ""

    def feed(self, chunk: str) -> str:
        """Append ``chunk`` and emit whatever text can be safely released."""
        if not chunk:
            return ""
        self._buf += chunk
        # Pull out every complete placeholder first.
        rewritten = _FULL_RE.sub(self._replace, self._buf)
        # Decide how much of the rewritten string we can emit. If the tail
        # could be the start of another placeholder, hold it back.
        partial = _PARTIAL_RE.search(rewritten)
        if partial is None:
            self._buf = ""
            return rewritten
        cut = partial.start()
        self._buf = rewritten[cut:]
        return rewritten[:cut]

    def flush(self) -> str:
        """Release any pending buffer content after the stream ends."""
        out = _FULL_RE.sub(self._replace, self._buf)
        self._buf = ""
        return out

    def _replace(self, m: re.Match[str]) -> str:
        placeholder = m.group(0)
        original = self._mint.resolve(placeholder)
        return original if original is not None else placeholder
