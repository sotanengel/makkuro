from __future__ import annotations

from makkuro.detectors.secrets import make_secret_detectors
from makkuro.pipeline import run_detectors


def _types(text: str) -> list[str]:
    return sorted(d.type for d in run_detectors(make_secret_detectors(), text))


class TestAnthropicKey:
    def test_detects(self):
        text = "my key is sk-ant-" + "A" * 100 + " thanks"
        assert "ANTHROPIC_API_KEY" in _types(text)

    def test_too_short_rejected(self):
        # Anthropic tail requires at least 40 chars; a stubby "sk-ant-abc"
        # should fall through without matching the Anthropic rule. It may
        # still match the looser openai pattern, so assert only Anthropic
        # is absent.
        hits = [
            d
            for d in run_detectors(make_secret_detectors(), "try sk-ant-abc now")
            if d.type == "ANTHROPIC_API_KEY"
        ]
        assert hits == []


class TestOpenAIKey:
    def test_proj_key(self):
        text = "OPENAI_API_KEY=sk-proj-" + "b" * 40 + " done"
        assert "OPENAI_API_KEY" in _types(text)


class TestAWSKey:
    def test_access_key(self):
        text = "use AKIAIOSFODNN7EXAMPLE for access"
        assert "AWS_ACCESS_KEY" in _types(text)


class TestGitHubToken:
    def test_ghp(self):
        text = "push with ghp_" + "A" * 36 + " please"
        assert "GITHUB_TOKEN" in _types(text)


class TestGoogleApiKey:
    def test_aiza(self):
        text = "google_api_key: AIza" + "b" * 35 + " here"
        assert "GOOGLE_API_KEY" in _types(text)


class TestJWT:
    def test_three_parts(self):
        text = "Bearer eyJhbGciOiJIUzI1NiJ9." + "A" * 20 + "." + "B" * 20
        assert "JWT" in _types(text)


class TestPEM:
    def test_block_captured(self):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEAxyz\n"
            "-----END RSA PRIVATE KEY-----"
        )
        assert "PEM_PRIVATE_KEY" in _types(text)


class TestNegatives:
    def test_plain_text_does_not_match(self):
        assert _types("hello world, no secrets here.") == []

    def test_random_alpha_string_rejected(self):
        # A 40-char alphabetic string is not enough: our Anthropic / OpenAI
        # rules require the sk- prefix.
        assert _types("noise: " + "A" * 40) == []
