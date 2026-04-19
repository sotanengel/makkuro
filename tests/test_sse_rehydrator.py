from __future__ import annotations

from makkuro.placeholder import PlaceholderMint
from makkuro.proxy.sse import SSERehydrator


def test_feed_simple():
    mint = PlaceholderMint()
    ph = mint.mint("EMAIL", "foo@example.com")
    r = SSERehydrator(mint)
    out = r.feed(f"text {ph} more")
    assert "foo@example.com" in out
    assert ph not in out


def test_split_placeholder_is_held():
    mint = PlaceholderMint()
    ph = mint.mint("EMAIL", "foo@example.com")
    mid = len(ph) // 2
    a, b = ph[:mid], ph[mid:]

    r = SSERehydrator(mint)
    first = r.feed(f"pre {a}")
    second = r.feed(f"{b} post")
    combined = first + second
    assert "foo@example.com" in combined
    assert ph not in combined


def test_unknown_placeholder_passes_through():
    mint = PlaceholderMint()
    r = SSERehydrator(mint)
    bogus = "<MAKKURO_EMAIL_deadbeef>"
    out = r.feed(f"x {bogus} y") + r.flush()
    # An unknown placeholder is returned verbatim; the stream is never
    # corrupted by an unmappable token.
    assert bogus in out


def test_flush_releases_partial_tail():
    mint = PlaceholderMint()
    r = SSERehydrator(mint)
    # A stray `<MAKK` at EOF must not get swallowed forever.
    out = r.feed("pre <MAKK")
    assert out == "pre "
    tail = r.flush()
    assert tail == "<MAKK"


def test_no_lookback_when_no_sentinel():
    mint = PlaceholderMint()
    r = SSERehydrator(mint)
    out = r.feed("nothing special here")
    assert out == "nothing special here"


def test_split_placeholder_with_underscore_type():
    """Placeholders like JP_MOBILE whose hash contains a-f must be held back."""
    mint = PlaceholderMint()
    ph = mint.mint("JP_MOBILE", "090-1234-5678")
    # Split inside the 8-char hex hash so the tail has lowercase hex digits.
    split = ph.index("_", len("<MAKKURO_JP_MOBILE")) + 3  # 3 hex chars in
    a, b = ph[:split], ph[split:]

    r = SSERehydrator(mint)
    first = r.feed(f"call {a}")
    second = r.feed(f"{b} ok") + r.flush()
    combined = first + second
    assert "090-1234-5678" in combined
    assert ph not in combined
