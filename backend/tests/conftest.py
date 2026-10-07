"""Shared fixtures.

Database fixtures require SLIP_TEST_DATABASE_URL pointing at a throwaway database whose name ends in
``_test``: the suite drops and recreates every table in it.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import make_engine, make_session_factory

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("SLIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "SLIP_TEST_DATABASE_URL is not set (integration tests need PostgreSQL + pgvector)"
        )
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        pytest.fail(
            f"Refusing to run destructive tests against database '{name}' (must end in _test)"
        )
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    config = alembic_config(database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = make_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(migrated_engine: Engine) -> sessionmaker[Session]:
    with migrated_engine.begin() as connection:
        connection.execute(text("TRUNCATE papers, documents, chunks, ingestion_jobs CASCADE"))
    return make_session_factory(migrated_engine)
