from __future__ import annotations

from datetime import UTC, datetime

import pytest
from footballpulse_crawler_service.discovery.rss import RssParseError, parse_rss


def test_parses_bounded_rss_entry_fields() -> None:
    payload = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>Football</title>
      <item><guid>story-1</guid><title> Transfer update </title>
      <link>https://news.example.com/story-1</link>
      <pubDate>Sun, 09 Aug 2026 01:02:03 GMT</pubDate>
      <description>Content that must not enter discovery output.</description></item>
    </channel></rss>"""

    parsed = parse_rss(payload, allowed_domains=("example.com",), max_entries=10)

    assert parsed.feed_title == "Football"
    assert parsed.parse_warning is None
    assert parsed.entries[0].guid == "story-1"
    assert parsed.entries[0].title == "Transfer update"
    assert parsed.entries[0].url == "https://news.example.com/story-1"
    assert parsed.entries[0].published_at == datetime(2026, 8, 9, 1, 2, 3, tzinfo=UTC)
    assert not hasattr(parsed.entries[0], "content")


def test_skips_entry_outside_allowlist_and_caps_output() -> None:
    payload = b"""<rss><channel>
      <item><guid>bad</guid><title>Bad</title><link>https://evil.test/a</link></item>
      <item><guid>one</guid><title>One</title><link>https://news.example.com/one</link></item>
      <item><guid>two</guid><title>Two</title><link>https://news.example.com/two</link></item>
    </channel></rss>"""

    parsed = parse_rss(payload, allowed_domains=("example.com",), max_entries=1)

    assert [entry.guid for entry in parsed.entries] == ["one"]
    assert parsed.skipped_entries == 1
    assert parsed.truncated is True


def test_keeps_usable_entries_from_malformed_feed_with_warning() -> None:
    payload = b"<rss><channel><item><title>One</title><link>https://news.example.com/one</link>"

    parsed = parse_rss(payload, allowed_domains=("example.com",), max_entries=10)

    assert len(parsed.entries) == 1
    assert parsed.parse_warning is not None


def test_rejects_malformed_feed_without_usable_entries() -> None:
    with pytest.raises(RssParseError):
        parse_rss(b"not a feed", allowed_domains=("example.com",), max_entries=10)
