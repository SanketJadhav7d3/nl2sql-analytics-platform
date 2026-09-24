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

# Separate engines authenticated as the read-only Postgres role, one per
# dataset's analytics schema (search_path pinned so unqualified table names in
# generated/ad-hoc SQL resolve to the right dataset). Used to execute /query,
# /nl-query, and /story SQL so least-privilege is enforced by the database
# itself. Built lazily/cached since most processes only ever touch one schema.
_readonly_engines: dict[str, Engine] = {}


def get_readonly_engine(schema: str = "analytics") -> Engine:
    if schema not in _readonly_engines:
        _readonly_engines[schema] = create_engine(
            settings.readonly_url,
            pool_pre_ping=True,
            future=True,
            connect_args={"options": f"-c search_path={schema}"},
        )
    return _readonly_engines[schema]


# Back-compat alias for the default (Olist) dataset.
readonly_engine: Engine = get_readonly_engine("analytics")


def get_conn() -> Iterator[Connection]:
    """Yield a read-only connection for the duration of a request."""
    with engine.connect() as conn:
        yield conn
