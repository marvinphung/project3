from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Role(StrEnum):
    EDITOR = "EDITOR"
    ADMIN = "ADMIN"


_PASSWORD_HASHER = PasswordHasher()


def _text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class User:
    username: str
    password_hash: str
    role: Role
    created_at: datetime

    @classmethod
    def create(cls, username: str, password: str, role: Role, *, created_at: datetime) -> User:
        timestamp = created_at
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return cls(
            username=_text(username, "username"),
            password_hash=_PASSWORD_HASHER.hash(_text(password, "password")),
            role=role,
            created_at=timestamp,
        )


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def add(self, user: User) -> None:
        if user.username in self._users:
            raise ValueError("username already exists")
        self._users[user.username] = user

    def get(self, username: str) -> User | None:
        return self._users.get(username)


class UserRepository(Protocol):
    def get(self, username: str) -> User | None: ...


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: str
    role: Role
    issued_at: datetime
    expires_at: datetime


class TokenService:
    def __init__(
        self,
        secret: str,
        *,
        issuer: str = "footballpulse-api",
        ttl: timedelta = timedelta(minutes=30),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT secret must be at least 32 bytes")
        if ttl.total_seconds() <= 0:
            raise ValueError("JWT TTL must be positive")
        self._secret = secret
        self._issuer = issuer
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(self, *, subject: str, role: Role, now: datetime | None = None) -> str:
        issued_at = now or self._clock()
        expires_at = issued_at + self._ttl
        return jwt.encode(
            {
                "sub": subject,
                "role": role.value,
                "iat": int(issued_at.timestamp()),
                "exp": int(expires_at.timestamp()),
                "iss": self._issuer,
            },
            self._secret,
            algorithm="HS256",
        )

    def decode(self, token: str, *, now: datetime | None = None) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=self._issuer,
                options={
                    "require": ["sub", "role", "iat", "exp", "iss"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
            expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
            current = now or self._clock()
            if current >= expires_at:
                raise ValueError("token expired")
            return TokenClaims(payload["sub"], Role(payload["role"]), issued_at, expires_at)
        except ValueError:
            raise
        except (jwt.InvalidTokenError, KeyError, TypeError, OSError) as error:
            raise ValueError("invalid token") from error


class AuthService:
    def __init__(self, users: UserRepository, tokens: TokenService) -> None:
        self._users = users
        self.tokens = tokens

    def authenticate(self, username: str, password: str) -> str:
        user = self._users.get(username)
        if user is None:
            raise ValueError("invalid credentials")
        try:
            _PASSWORD_HASHER.verify(user.password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError) as error:
            raise ValueError("invalid credentials") from error
        return self.tokens.issue(subject=user.username, role=user.role)
