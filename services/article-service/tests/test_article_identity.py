from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_article_service.domain.article import (
    ExistingArticleVersion,
    VersionDecisionKind,
    canonicalize_article_url,
    decide_article_version,
)


def test_canonicalizes_host_default_port_fragment_and_tracking_parameters() -> None:
    canonical = canonicalize_article_url(
        "HTTPS://News.Example.COM:443/football/story?utm_source=rss&b=2&a=1#comments"
    )

    assert canonical == "https://news.example.com/football/story?a=1&b=2"


def test_preserves_non_tracking_query_and_repeated_values() -> None:
    canonical = canonicalize_article_url(
        "https://news.example.com/story?tag=transfer&tag=arsenal&fbclid=ignored"
    )

    assert canonical == "https://news.example.com/story?tag=arsenal&tag=transfer"


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:secret@news.example.com/story",
        "https:///missing-host",
    ],
)
def test_rejects_url_outside_article_identity_boundary(url: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_article_url(url)


def test_first_content_creates_stable_article_and_version_identity() -> None:
    first = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Arsenal submitted a €180m offer.",
        latest=None,
    )
    replayed_decision = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Arsenal submitted a €180m offer.",
        latest=None,
    )

    assert first.kind is VersionDecisionKind.CREATED
    assert first.article_id == replayed_decision.article_id
    assert first.article_version_id == replayed_decision.article_version_id
    assert first.version == 1
    assert first.previous_version_id is None
    assert len(first.content_hash) == 64


def test_same_hash_returns_unchanged_existing_version() -> None:
    first = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Arsenal submitted a €180m offer.",
        latest=None,
    )
    latest = ExistingArticleVersion(
        article_id=first.article_id,
        article_version_id=first.article_version_id,
        version=3,
        content_hash="827822547c01705f9f13da485d357dc4395633b0206e79cbb2055b17686718cc",
    )

    decision = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Arsenal submitted a €180m offer.",
        latest=latest,
    )

    assert decision.kind is VersionDecisionKind.UNCHANGED
    assert decision.article_id == latest.article_id
    assert decision.article_version_id == latest.article_version_id
    assert decision.version == 3
    assert decision.previous_version_id is None


def test_changed_hash_creates_next_version_link() -> None:
    first = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Earlier report.",
        latest=None,
    )
    latest = ExistingArticleVersion(
        article_id=first.article_id,
        article_version_id=first.article_version_id,
        version=3,
        content_hash="old-hash",
    )

    decision = decide_article_version(
        canonical_url="https://news.example.com/story",
        cleaned_content="Real Madrid rejected the offer.",
        latest=latest,
    )

    assert decision.kind is VersionDecisionKind.CREATED
    assert decision.article_id == latest.article_id
    assert decision.version == 4
    assert decision.previous_version_id == latest.article_version_id


def test_rejects_latest_version_from_different_canonical_identity() -> None:
    latest = ExistingArticleVersion(
        article_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3c4101"),
        article_version_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3c4201"),
        version=1,
        content_hash="827822547c01705f9f13da485d357dc4395633b0206e79cbb2055b17686718cc",
    )

    with pytest.raises(ValueError, match="identity"):
        decide_article_version(
            canonical_url="https://news.example.com/story",
            cleaned_content="Arsenal submitted a €180m offer.",
            latest=latest,
        )
