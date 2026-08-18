from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid5

NEWS_URL_NAMESPACE = UUID("5f0d8d26-c499-4b2c-b390-83178a85d814")
_TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize_news_url(value: str) -> str:
    """Return the stable URL representation used for article deduplication."""
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 2083:
        raise ValueError("news URL must contain 1 to 2083 characters")

    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("news URL must use HTTP or HTTPS and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("news URL must not contain credentials")

    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("news URL host or port is invalid") from exc
    if not host:
        raise ValueError("news URL host is invalid")
    if port == (443 if scheme == "https" else 80):
        port = None

    host_literal = f"[{host}]" if ":" in host else host
    netloc = f"{host_literal}:{port}" if port is not None else host_literal
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMETERS
    ]
    query.sort()
    return urlunsplit((scheme, netloc, parsed.path or "/", urlencode(query), ""))


def article_id_from_url(value: str) -> UUID:
    return uuid5(NEWS_URL_NAMESPACE, canonicalize_news_url(value))
