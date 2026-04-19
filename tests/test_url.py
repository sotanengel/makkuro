from __future__ import annotations

from makkuro.detectors.url import URLDetector


class TestURLDetector:
    def setup_method(self):
        self.det = URLDetector()

    def test_userinfo_http(self):
        hits = self.det.scan("connect to http://admin:s3cret@db.internal:5432/mydb")
        assert len(hits) == 1
        assert hits[0].type == "URL_CREDENTIAL"
        assert "admin:s3cret@" in hits[0].value

    def test_userinfo_https(self):
        hits = self.det.scan("url: https://user:pass@example.com/path")
        assert len(hits) == 1
        assert hits[0].score == 0.95

    def test_token_param(self):
        hits = self.det.scan("https://api.example.com/v1/data?token=abc123xyz")
        assert len(hits) == 1
        assert hits[0].type == "URL_CREDENTIAL"

    def test_api_key_param(self):
        hits = self.det.scan("https://maps.example.com/api?api_key=MY_KEY_123")
        assert len(hits) == 1

    def test_password_param(self):
        hits = self.det.scan("https://login.example.com?password=hunter2")
        assert len(hits) == 1

    def test_access_token_param(self):
        hits = self.det.scan("https://api.example.com/cb?access_token=eyJhbG")
        assert len(hits) == 1

    def test_ignores_plain_url(self):
        assert self.det.scan("visit https://example.com/page") == []

    def test_ignores_plain_url_with_query(self):
        assert self.det.scan("https://example.com?page=1&sort=asc") == []

    def test_multiple(self):
        text = (
            "db: http://root:pass@db:3306 "
            "api: https://svc.io/v1?key=abc"
        )
        hits = self.det.scan(text)
        assert len(hits) == 2

    def test_strips_trailing_punctuation(self):
        hits = self.det.scan("See http://user:pw@host.com/path.")
        assert len(hits) == 1
        assert not hits[0].value.endswith(".")

    def test_case_insensitive_param(self):
        hits = self.det.scan("https://x.io/api?Token=abc123")
        assert len(hits) == 1

    def test_auth_param(self):
        hits = self.det.scan("https://x.io/api?auth=secret_val")
        assert len(hits) == 1
