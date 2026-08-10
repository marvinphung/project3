from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from footballpulse_api_gateway.auth import (
    AuthService,
    InMemoryUserRepository,
    Role,
    TokenService,
    User,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
SECRET = "local-secret-012345678901234567890123"


def test_auth_service_hashes_password_and_issues_role_token() -> None:
    users = InMemoryUserRepository()
    users.add(User.create("editor", "correct horse", Role.EDITOR, created_at=NOW))
    service = AuthService(users, TokenService(SECRET, clock=lambda: NOW))

    token = service.authenticate("editor", "correct horse")
    claims = service.tokens.decode(token, now=NOW)

    assert claims.subject == "editor"
    assert claims.role is Role.EDITOR
    assert claims.expires_at > NOW


def test_auth_service_rejects_wrong_password_and_expired_token() -> None:
    users = InMemoryUserRepository()
    users.add(User.create("admin", "correct horse", Role.ADMIN, created_at=NOW))
    service = AuthService(users, TokenService(SECRET, clock=lambda: NOW))

    with pytest.raises(ValueError, match="invalid credentials"):
        service.authenticate("admin", "wrong")

    expiring = TokenService(SECRET, ttl=timedelta(seconds=1), clock=lambda: NOW)
    token = expiring.issue(subject="admin", role=Role.ADMIN, now=NOW)
    with pytest.raises(ValueError, match="expired"):
        expiring.decode(token, now=NOW + timedelta(seconds=2))
