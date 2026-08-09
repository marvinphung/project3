from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid5

_ARTICLE_NAMESPACE = UUID("5f0d8d26-c499-4b2c-b390-83178a85d814")
_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


class VersionDecisionKind(StrEnum):
    CREATED = "CREATED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class ExistingArticleVersion:
    article_id: UUID
    article_version_id: UUID
    version: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ArticleVersionDecision:
    kind: VersionDecisionKind
    article_id: UUID
    article_version_id: UUID
    version: int
    previous_version_id: UUID | None
    content_hash: str


def canonicalize_article_url(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 2083:
        raise ValueError("article URL must contain 1 to 2083 characters")
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("article URL must use HTTP or HTTPS and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("article URL must not contain credentials")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("article URL host or port is invalid") from exc
    if not host:
        raise ValueError("article URL host is invalid")
    if port == (443 if scheme == "https" else 80):
        port = None
    host_literal = f"[{host}]" if ":" in host else host
    netloc = f"{host_literal}:{port}" if port is not None else host_literal

    query_items = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMETERS
    ]
    query_items.sort()
    return urlunsplit((scheme, netloc, parsed.path or "/", urlencode(query_items), ""))


def decide_article_version(
    *,
    canonical_url: str,
    cleaned_content: str,
    latest: ExistingArticleVersion | None,
) -> ArticleVersionDecision:
    canonical = canonicalize_article_url(canonical_url)
    if not isinstance(cleaned_content, str) or not cleaned_content:
        raise ValueError("cleaned article content must not be empty")
    content_hash = hashlib.sha256(cleaned_content.encode("utf-8")).hexdigest()
    stable_article_id = uuid5(_ARTICLE_NAMESPACE, canonical)
    if latest is not None and latest.article_id != stable_article_id:
        raise ValueError("latest version does not belong to canonical article identity")
    if latest is not None and latest.content_hash == content_hash:
        return ArticleVersionDecision(
            VersionDecisionKind.UNCHANGED,
            latest.article_id,
            latest.article_version_id,
            latest.version,
            None,
            content_hash,
        )
    version = 1 if latest is None else latest.version + 1
    version_id = uuid5(stable_article_id, f"version:{version}:{content_hash}")
    return ArticleVersionDecision(
        VersionDecisionKind.CREATED,
        stable_article_id,
        version_id,
        version,
        latest.article_version_id if latest is not None else None,
        content_hash,
    )
