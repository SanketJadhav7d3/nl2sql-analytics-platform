"""Auth, RBAC and guardrail tests.

Bootstraps one user of each role via the admin API, then asserts the full
access matrix, the /query guardrails, and that audit rows are written.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.auth import manage, service


@pytest.fixture(scope="module", autouse=True)
def _init_auth():
    # Ensure schema + read-only role + default admin exist.
    manage.init()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def users(client: TestClient):
    """Create one viewer/analyst/admin (unique names) and return their tokens."""
    admin_token = _login(client, "admin", "admin123")
    sfx = uuid.uuid4().hex[:8]
    created = {}
    tokens = {"admin": admin_token}
    for role in ("viewer", "analyst", "admin"):
        uname = f"t_{role}_{sfx}"
        r = client.post(
            "/admin/users",
            headers=_auth(admin_token),
            json={"username": uname, "password": "pw123456", "role": role},
        )
        assert r.status_code == 201, r.text
        created[role] = r.json()["id"]
        tokens[f"new_{role}"] = _login(client, uname, "pw123456")

    yield tokens

    for uid in created.values():
        client.delete(f"/admin/users/{uid}", headers=_auth(admin_token))


# ---- authentication ---------------------------------------------------------
def test_login_bad_credentials(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_metrics_requires_token(client):
    assert client.get("/metrics/revenue").status_code == 401


def test_invalid_token_rejected(client):
    r = client.get("/metrics/revenue", headers=_auth("garbage.token.here"))
    assert r.status_code == 401


# ---- access matrix ----------------------------------------------------------
def test_viewer_can_read_metrics(client, users):
    r = client.get("/metrics/revenue", headers=_auth(users["new_viewer"]))
    assert r.status_code == 200


def test_viewer_denied_query(client, users):
    r = client.post("/query", headers=_auth(users["new_viewer"]),
                    json={"sql": "SELECT 1"})
    assert r.status_code == 403


def test_viewer_denied_admin(client, users):
    assert client.get("/admin/users", headers=_auth(users["new_viewer"])).status_code == 403


def test_analyst_can_query(client, users):
    r = client.post("/query", headers=_auth(users["new_analyst"]),
                    json={"sql": "SELECT category, revenue FROM vw_category_performance"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] > 0
    assert "category" in body["rows"][0]


def test_analyst_denied_admin(client, users):
    assert client.get("/admin/users", headers=_auth(users["new_analyst"])).status_code == 403


def test_admin_can_manage_users(client, users):
    r = client.get("/admin/users", headers=_auth(users["new_admin"]))
    assert r.status_code == 200
    assert any(u["role"] == "admin" for u in r.json())


# ---- /query guardrails ------------------------------------------------------
@pytest.mark.parametrize("sql", [
    "DELETE FROM analytics.fct_order_items",          # not a SELECT
    "UPDATE analytics.dim_product SET category='x'",  # write
    "DROP TABLE analytics.fct_order_items",           # DDL
    "SELECT 1; DROP TABLE analytics.dim_product",     # stacked statements
    "SELECT * FROM raw.orders",                        # disallowed schema
    "SELECT * FROM app.users",                         # disallowed schema
    "SELECT * FROM pg_catalog.pg_roles",               # not allow-listed
    "SELECT * FROM vw_category_performance -- sneaky",# comment
])
def test_query_guardrails_reject(client, users, sql):
    r = client.post("/query", headers=_auth(users["new_analyst"]), json={"sql": sql})
    assert r.status_code == 400, f"expected reject for: {sql} (got {r.status_code})"


def test_query_limit_is_enforced(client, users):
    # fct has 100k+ rows; the cap must bound the result.
    r = client.post("/query", headers=_auth(users["new_admin"]),
                    json={"sql": "SELECT order_id FROM fct_order_items"})
    assert r.status_code == 200
    assert r.json()["row_count"] <= 1000


# ---- audit log --------------------------------------------------------------
def test_audit_records_query(client, users):
    # run a distinctive query, then confirm it shows up in the audit log
    marker_sql = "SELECT category FROM vw_category_performance"
    client.post("/query", headers=_auth(users["new_analyst"]), json={"sql": marker_sql})

    r = client.get("/admin/audit-log", headers=_auth(users["new_admin"]),
                   params={"limit": 200})
    assert r.status_code == 200
    entries = r.json()
    assert any(e["action"] == "query" and e["status"] == "allowed"
               and e["detail"] == marker_sql for e in entries)


def test_audit_records_denied_access(client, users):
    # a viewer hitting /admin should be logged as denied
    client.get("/admin/users", headers=_auth(users["new_viewer"]))
    entries = service.list_audit(200)
    assert any(e["action"] == "GET /admin/users" and e["status"] == "denied"
               for e in entries)
