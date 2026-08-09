from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from footballpulse_crawler_service.domain.errors import DomainError, DomainValidationError
from footballpulse_crawler_service.domain.source import host_is_allowed, normalize_domain

Resolver = Callable[[str, int], Awaitable[tuple[str, ...]]]


class UnsafeUrlError(DomainError):
    """Raised before a network request when a URL crosses the safety boundary."""


@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


async def resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc
    return tuple(sorted({str(record[4][0]) for record in records}))


class UrlSafetyPolicy:
    def __init__(self, *, resolver: Resolver = resolve_public_addresses) -> None:
        self._resolver = resolver

    async def validate(
        self,
        url: str,
        *,
        allowed_domains: tuple[str, ...],
    ) -> ValidatedUrl:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise UnsafeUrlError("URL scheme must be http or https")
        if parsed.hostname is None:
            raise UnsafeUrlError("URL must include a host")
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeUrlError("URL credentials are not allowed")

        try:
            host = normalize_domain(parsed.hostname)
            explicit_port = parsed.port
        except (DomainValidationError, ValueError, UnicodeError) as exc:
            raise UnsafeUrlError("URL host or port is invalid") from exc
        port = explicit_port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise UnsafeUrlError("URL port must be 80 or 443")
        if not host_is_allowed(host, allowed_domains):
            raise UnsafeUrlError("URL host is outside the source allowlist")

        addresses = await self._resolver(host, port)
        if not addresses:
            raise UnsafeUrlError("URL host did not resolve to an address")
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError as exc:
                raise UnsafeUrlError("resolver returned an invalid IP address") from exc
            if not address.is_global:
                raise UnsafeUrlError("URL resolved to a non-public IP address")

        normalized_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")
        )
        return ValidatedUrl(normalized_url, host, port, addresses)

    async def validate_redirect(
        self,
        *,
        current_url: str,
        location: str,
        allowed_domains: tuple[str, ...],
    ) -> ValidatedUrl:
        return await self.validate(
            urljoin(current_url, location),
            allowed_domains=allowed_domains,
        )
