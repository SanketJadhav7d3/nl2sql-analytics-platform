"""NL-to-SQL guardrail tests.

A fake adapter substitutes for the LLM (injected via FastAPI dependency
override) so we can feed the exact SQL the "model" returns — including
malicious payloads — and assert the guardrails catch them. No API key needed.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.auth import manage
from src.api.main import app
from src.api.nl.adapter import LLMAdapter, get_adapter


class FakeAdapter(LLMAdapter):
    """Returns a preset SQL string, ignoring the question."""
    def __init__(self, sql: str):
        self.sql = sql

    def generate_sql(self, question: str, schema_prompt: str) -> str:
        return self.sql


@pytest.fixture(scope="module", autouse=True)
def _init_auth():
    manage.init()


@pytest.fixture(scope="module")
def analyst_token(client: TestClient) -> str:
    admin = client.post("/auth/login",
                        json={"username": "admin", "password": "admin123"}).json()["access_token"]
    uname = f"nlq_analyst_{uuid.uuid4().hex[:8]}"
    client.post("/admin/users", headers={"Authorization": f"Bearer {admin}"},
                json={"username": uname, "password": "pw123456", "role": "analyst"})
    return client.post("/auth/login",
                       json={"username": uname, "password": "pw123456"}).json()["access_token"]


def _ask(client, token, sql_to_return, question="anything"):
    """Override the adapter to return `sql_to_return`, then call /nl-query."""
    app.dependency_overrides[get_adapter] = lambda: FakeAdapter(sql_to_return)
    try:
        return client.post("/nl-query",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"question": question})
    finally:
        app.dependency_overrides.pop(get_adapter, None)


# ---- happy path -------------------------------------------------------------
def test_valid_select_returns_sql_and_rows(client, analyst_token):
    r = _ask(client, analyst_token,
             "SELECT category, revenue FROM vw_category_performance ORDER BY revenue DESC LIMIT 5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sql"].startswith("SELECT")        # generated SQL returned for transparency
    assert body["row_count"] > 0
    assert "category" in body["rows"][0]


def test_markdown_fences_are_stripped(client, analyst_token):
    r = _ask(client, analyst_token,
             "```sql\nSELECT category FROM vw_category_performance LIMIT 3\n```")
    assert r.status_code == 200, r.text
    assert "`" not in r.json()["sql"]


def test_extract_from_column_is_not_mistaken_for_a_table(client, analyst_token):
    # Regression: EXTRACT(year FROM order_month) must NOT trip the table allow-list.
    r = _ask(client, analyst_token,
             "SELECT order_month, revenue FROM vw_monthly_revenue "
             "WHERE EXTRACT(year FROM order_month) = 2018 ORDER BY order_month LIMIT 12")
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] > 0


def test_limit_is_enforced_even_if_model_omits_it(client, analyst_token):
    # fct has 100k+ rows and the model "forgot" LIMIT -> wrapper must cap it.
    r = _ask(client, analyst_token, "SELECT order_id FROM fct_order_items")
    assert r.status_code == 200
    assert r.json()["row_count"] <= 1000


# ---- guardrails: malicious / invalid generations ----------------------------
@pytest.mark.parametrize("malicious_sql", [
    "DELETE FROM analytics.fct_order_items",                 # not a SELECT
    "UPDATE analytics.dim_product SET category = 'x'",       # write
    "DROP TABLE analytics.fct_order_items",                  # DDL
    "TRUNCATE analytics.fct_order_items",                    # DDL
    "SELECT 1; DROP TABLE analytics.dim_product",            # stacked statements
    "SELECT * FROM raw.orders",                               # disallowed schema (raw)
    "SELECT * FROM app.users",                                # disallowed schema (app)
    "SELECT * FROM pg_catalog.pg_roles",                      # not allow-listed
    "SELECT * FROM vw_category_performance -- exfiltrate",   # SQL comment
    "INSERT INTO analytics.dim_seller VALUES ('x')",          # write
])
def test_guardrails_reject_malicious_generation(client, analyst_token, malicious_sql):
    r = _ask(client, analyst_token, malicious_sql)
    assert r.status_code == 400, f"expected reject for: {malicious_sql} (got {r.status_code})"
    assert "guardrail" in r.json()["detail"].lower()


# ---- RBAC: viewer may not use NL-to-SQL -------------------------------------
def test_viewer_denied(client):
    viewer_admin = client.post("/auth/login",
                               json={"username": "admin", "password": "admin123"}).json()["access_token"]
    uname = f"nlq_viewer_{uuid.uuid4().hex[:8]}"
    client.post("/admin/users", headers={"Authorization": f"Bearer {viewer_admin}"},
                json={"username": uname, "password": "pw123456", "role": "viewer"})
    vt = client.post("/auth/login",
                     json={"username": uname, "password": "pw123456"}).json()["access_token"]
    r = _ask(client, vt, "SELECT 1 FROM vw_category_performance LIMIT 1")
    assert r.status_code == 403
