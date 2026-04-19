"""JSONL audit log writer.

Per spec §4 F6, audit entries record placeholder, detection type, detector
name, score, timestamp, and request ID — but never the plaintext value or
the vault mapping. The log is safe to share in bug reports.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class AuditEvent:
    event: str
    placeholder: str = ""
    type: str = ""
    detector: str = ""
    score: float = 0.0
    request_id: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "ts": datetime.now(tz=UTC).isoformat(timespec="milliseconds"),
            "event": self.event,
        }
        if self.request_id:
            out["request_id"] = self.request_id
        if self.placeholder:
            out["placeholder"] = self.placeholder
        if self.type:
            out["type"] = self.type
        if self.detector:
            out["detector"] = self.detector
        if self.score:
            out["score"] = round(self.score, 3)
        if self.extra:
            out["extra"] = self.extra
        return out


class AuditWriter:
    """Appends ``AuditEvent``s to a JSONL file, one per line.

    Thread-safe via an internal mutex. ``enabled=False`` disables all I/O;
    passing ``path=None`` writes to an in-memory buffer (used by tests).
    """

    def __init__(
        self,
        path: Path | None,
        enabled: bool = True,
    ) -> None:
        self.path = path
        self.enabled = enabled
        self._lock = threading.Lock()
        self._buffer: list[dict[str, object]] = []
        if self.path is not None and self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Touch the file so later readers don't race on nonexistence.
            if not self.path.exists():
                self.path.touch(mode=0o600)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def write(self, event: AuditEvent) -> None:
        if not self.enabled:
            return
        payload = event.to_dict()
        with self._lock:
            self._buffer.append(payload)
            if self.path is not None:
                with self.path.open("a", encoding="utf-8") as h:
                    h.write(json.dumps(payload, ensure_ascii=False))
                    h.write("\n")

    def buffered(self) -> list[dict[str, object]]:
        """Return a copy of every event seen so far (memory + file)."""
        with self._lock:
            return list(self._buffer)

    def flush(self) -> None:  # Python's text-mode files flush on close anyway.
        return None
