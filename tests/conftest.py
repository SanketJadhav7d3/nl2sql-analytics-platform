"""Shared pytest fixtures.

Tests run against the loaded warehouse (integration-style), which is the honest
way to prove the reporting SQL is correct. If the DB is unreachable the whole
module is skipped with a clear message rather than failing noisily.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.api.db import engine
from src.api.main import app


@pytest.fixture(scope="session", autouse=True)
def _require_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM analytics.fct_order_items LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"warehouse not available ({exc}); run the loader first")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
