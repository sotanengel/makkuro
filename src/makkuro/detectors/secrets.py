"""Secret and API-key detectors inspired by the gitleaks rule set.

Each pattern is anchored with context lookarounds so a 40-character random
string in running prose doesn't trigger. The patterns target the common
prefix + opaque tail shape of modern API keys, which is both the highest
signal and the lowest false-positive profile.
"""

from __future__ import annotations

import re

from makkuro.detectors.base import Detection

# Anthropic keys: ``sk-ant-...``
ANTHROPIC_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"sk-ant-[A-Za-z0-9_-]{40,200}"
    r"(?![A-Za-z0-9_-])"
)

# OpenAI-style project keys (sk-proj-..., sk-svcacct-..., sk-...)
OPENAI_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"sk-(?:proj-|svcacct-|admin-|None-)?[A-Za-z0-9_-]{20,200}"
    r"(?![A-Za-z0-9_-])"
)

# Google API keys: AIza + 35 chars
GOOGLE_API_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"AIza[A-Za-z0-9_-]{35}"
    r"(?![A-Za-z0-9_-])"
)

# AWS access key IDs: AKIA|ASIA + 16 upper-alnum
AWS_ACCESS_KEY_RE = re.compile(
    r"(?<![A-Z0-9])"
    r"(?:AKIA|ASIA|AIDA|AROA|ANPA|ANVA)[A-Z0-9]{16}"
    r"(?![A-Z0-9])"
)

# GitHub classic / fine-grained / OAuth tokens
GITHUB_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,76}"
    r"(?![A-Za-z0-9_-])"
)

# Slack bot / user tokens
SLACK_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"xox[abpors]-[A-Za-z0-9-]{10,200}"
    r"(?![A-Za-z0-9_-])"
)

# Stripe live keys
STRIPE_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"sk_live_[A-Za-z0-9]{24,99}"
    r"(?![A-Za-z0-9_-])"
)

# JWT: three dot-separated base64url segments, header/payload both JSON-ish
JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"(?![A-Za-z0-9_-])"
)

# PEM private key blocks
PEM_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    r"[\s\S]+?"
    r"-----END (?:RSA |DSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)


class _PatternDetector:
    def __init__(self, name: str, entity_type: str, pattern: re.Pattern[str], score: float):
        self.name = name
        self.entity_type = entity_type
        self._re = pattern
        self._score = score

    def scan(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for m in self._re.finditer(text):
            out.append(
                Detection(
                    type=self.entity_type,
                    start=m.start(),
                    end=m.end(),
                    score=self._score,
                    detector=self.name,
                    value=m.group(0),
                )
            )
        return out


def make_secret_detectors() -> list[_PatternDetector]:
    return [
        _PatternDetector("anthropic_key", "ANTHROPIC_API_KEY", ANTHROPIC_KEY_RE, 0.99),
        # Anthropic keys start with "sk-ant-"; put the generic OpenAI rule
        # afterwards so the more specific match wins at equal span length.
        _PatternDetector("openai_key", "OPENAI_API_KEY", OPENAI_KEY_RE, 0.95),
        _PatternDetector("google_api_key", "GOOGLE_API_KEY", GOOGLE_API_KEY_RE, 0.98),
        _PatternDetector("aws_access_key", "AWS_ACCESS_KEY", AWS_ACCESS_KEY_RE, 0.99),
        _PatternDetector("github_token", "GITHUB_TOKEN", GITHUB_TOKEN_RE, 0.99),
        _PatternDetector("slack_token", "SLACK_TOKEN", SLACK_TOKEN_RE, 0.98),
        _PatternDetector("stripe_key", "STRIPE_KEY", STRIPE_KEY_RE, 0.99),
        _PatternDetector("jwt", "JWT", JWT_RE, 0.9),
        _PatternDetector("pem_private_key", "PEM_PRIVATE_KEY", PEM_PRIVATE_KEY_RE, 1.0),
    ]
