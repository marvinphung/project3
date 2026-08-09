from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.schema import CreateSchema

SCHEMA_NAME = "source_schema"
VERSION_TABLE = "alembic_version_source"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    explicit_url = os.getenv("FOOTBALLPULSE_DATABASE_URL")
    if explicit_url:
        return explicit_url
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    ).render_as_string(hide_password=False)


def configure_migrations(**kwargs: object) -> None:
    context.configure(
        target_metadata=None,
        version_table=VERSION_TABLE,
        version_table_schema=SCHEMA_NAME,
        include_schemas=True,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    configure_migrations(
        url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with create_engine(database_url(), pool_pre_ping=True).begin() as connection:
        connection.execute(CreateSchema(SCHEMA_NAME, if_not_exists=True))
        configure_migrations(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
