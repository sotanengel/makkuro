"""URL detector for credentials and tokens leaked in URLs.

Detects ``http://`` and ``https://`` URLs that contain embedded
credentials (``user:pass@host``) or sensitive-looking query parameters
(``token=``, ``key=``, ``secret=``, ``password=``, ``api_key=``).
Plain URLs without credentials or sensitive params are ignored to
reduce noise.
"""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

# Match http(s) URLs; generous path/query capture.
_URL_RE = re.compile(
    r"https?://"
    r"[^\s\"'<>\x00-\x1f]{4,500}"
)

# userinfo component: ``user:password@``
_USERINFO_RE = re.compile(
    r"^https?://[^/:@]+:[^/:@]+@"
)

# Query-string keys that commonly hold secrets.
_SENSITIVE_PARAMS_RE = re.compile(
    r"[?&](?:token|key|secret|password|passwd|api_key|apikey|access_token|auth)"
    r"=",
    re.IGNORECASE,
)


class URLDetector:
    """Detect URLs containing embedded credentials or sensitive query params."""

    name = "url_credential"
    entity_type = "URL_CREDENTIAL"

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in _URL_RE.finditer(text):
            raw = m.group(0)
            # Strip trailing punctuation that is likely sentence-level.
            raw = raw.rstrip(".,;:!?)>]}\"'")
            if not raw:
                continue
            has_userinfo = bool(_USERINFO_RE.search(raw))
            has_sensitive_param = bool(_SENSITIVE_PARAMS_RE.search(raw))
            if not has_userinfo and not has_sensitive_param:
                continue
            score = 0.95 if has_userinfo else 0.88
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.start() + len(raw),
                    score=score,
                    detector=self.name,
                    value=raw,
                )
            )
        return out
