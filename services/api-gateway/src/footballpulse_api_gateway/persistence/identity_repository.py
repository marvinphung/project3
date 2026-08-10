from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Engine, RowMapping

from footballpulse_api_gateway.auth import Role, User
from footballpulse_api_gateway.persistence.identity_tables import users


def _from_row(row: RowMapping) -> User:
    return User(
        username=row["username"],
        password_hash=row["password_hash"],
        role=Role(row["role"]),
        created_at=row["created_at"],
    )


class PostgresUserRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, username: str) -> User | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(users).where(users.c.username == username))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _from_row(row)
