from __future__ import annotations

from makkuro.detectors.base import Detection
from makkuro.placeholder import PlaceholderMint, rehydrate, substitute


def _det(t: str, start: int, end: int, value: str) -> Detection:
    return Detection(type=t, start=start, end=end, score=0.99, detector="x", value=value)


class TestMint:
    def test_same_value_same_placeholder(self):
        m = PlaceholderMint()
        a = m.mint("EMAIL", "foo@example.com")
        b = m.mint("EMAIL", "foo@example.com")
        assert a == b

    def test_different_value_different_placeholder(self):
        m = PlaceholderMint()
        a = m.mint("EMAIL", "a@x.jp")
        b = m.mint("EMAIL", "b@x.jp")
        assert a != b

    def test_placeholder_format(self):
        m = PlaceholderMint()
        p = m.mint("EMAIL", "foo@example.com")
        assert p.startswith("<MAKKURO_EMAIL_")
        assert p.endswith(">")


class TestSubstitute:
    def test_basic(self):
        m = PlaceholderMint()
        text = "hello foo@example.com bye"
        d = _det("EMAIL", 6, 21, "foo@example.com")
        out = substitute(text, [d], m)
        assert "foo@example.com" not in out
        assert out.startswith("hello <MAKKURO_EMAIL_")
        assert out.endswith(" bye")

    def test_multiple_back_to_front(self):
        m = PlaceholderMint()
        text = "a@b.jp then c@d.jp"
        d1 = _det("EMAIL", 0, 6, "a@b.jp")
        d2 = _det("EMAIL", 12, 18, "c@d.jp")
        out = substitute(text, [d2, d1], m)
        assert "a@b.jp" not in out
        assert "c@d.jp" not in out
        assert out.count("<MAKKURO_EMAIL_") == 2


class TestRehydrate:
    def test_round_trip(self):
        m = PlaceholderMint()
        text = "連絡先 foo@example.com と 090-0000-1111"
        d1 = _det("EMAIL", 4, 19, "foo@example.com")
        d2 = _det("JP_MOBILE", 22, 35, "090-0000-1111")
        redacted = substitute(text, [d1, d2], m)
        restored, unknown = rehydrate(redacted, m)
        assert restored == text
        assert unknown == []

    def test_unknown_placeholder(self):
        m = PlaceholderMint()
        restored, unknown = rehydrate("pre <MAKKURO_EMAIL_deadbeef> post", m)
        assert "<MAKKURO_EMAIL_deadbeef>" in restored
        assert unknown == ["<MAKKURO_EMAIL_deadbeef>"]
