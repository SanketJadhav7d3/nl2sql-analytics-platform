"""SQLAlchemy engine + a FastAPI connection dependency.

A single Engine (with a pooled connection) is created at import time. Each
request gets a short-lived Connection via `get_conn`; the reporting layer is
read-only, so we never open write transactions here.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection

from .config import settings

engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

# Separate engine authenticated as the read-only Postgres role, with the search
# path pinned to `analytics`. Used to execute ad-hoc /query and /nl-query SQL so
# least-privilege is enforced by the database itself.
readonly_engine: Engine = create_engine(
    settings.readonly_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"options": "-c search_path=analytics"},
)


def get_conn() -> Iterator[Connection]:
    """Yield a read-only connection for the duration of a request."""
    with engine.connect() as conn:
        yield conn
