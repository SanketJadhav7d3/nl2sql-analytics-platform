"""Endpoint logic tests for the /metrics/* reporting API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.auth import manage
from src.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Authenticated client (admin) — metrics now require a bearer token.

    This module-local fixture overrides the unauthenticated one in conftest.
    """
    manage.init()  # ensure schema + seeded admin
    c = TestClient(app)
    token = c.post("/auth/login",
                   json={"username": "admin", "password": "admin123"}).json()["access_token"]
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---- /metrics/revenue -------------------------------------------------------
def test_revenue_default_month(client):
    r = client.get("/metrics/revenue")
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "month"
    pts = body["points"]
    assert len(pts) > 0
    # periods are sorted ascending
    periods = [p["period"] for p in pts]
    assert periods == sorted(periods)
    # running total is monotonically non-decreasing and equals the cumulative sum
    cum = 0.0
    for p in pts:
        cum += p["revenue"]
        assert p["running_total_revenue"] == pytest.approx(cum, rel=1e-6)
    # first point has no prior month -> no growth figure
    assert pts[0]["mom_growth_pct"] is None


def test_revenue_granularity_and_date_filter(client):
    r = client.get("/metrics/revenue", params={"granularity": "day",
                                               "from": "2017-01-01",
                                               "to": "2017-01-31"})
    assert r.status_code == 200
    pts = r.json()["points"]
    assert pts, "expected daily points in Jan 2017"
    for p in pts:
        assert "2017-01-01" <= p["period"] <= "2017-01-31"


def test_revenue_rejects_bad_granularity(client):
    # pattern validation should reject anything outside the whitelist (also our
    # guard against SQL-keyword injection on date_trunc).
    r = client.get("/metrics/revenue", params={"granularity": "year; DROP TABLE"})
    assert r.status_code == 422


# ---- /metrics/categories/top ------------------------------------------------
def test_top_categories_limit_and_rank(client):
    r = client.get("/metrics/categories/top", params={"limit": 5})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 5
    # ranked 1..5 and revenue strictly non-increasing
    assert [row["revenue_rank"] for row in rows] == [1, 2, 3, 4, 5]
    revs = [row["revenue"] for row in rows]
    assert revs == sorted(revs, reverse=True)
    # revenue share is a sensible percentage
    for row in rows:
        assert 0 <= row["revenue_share_pct"] <= 100


def test_top_categories_limit_bounds(client):
    assert client.get("/metrics/categories/top", params={"limit": 0}).status_code == 422
    assert client.get("/metrics/categories/top", params={"limit": 999}).status_code == 422


# ---- /metrics/aov -----------------------------------------------------------
def test_aov_overall_and_breakdowns(client):
    r = client.get("/metrics/aov")
    assert r.status_code == 200
    body = r.json()
    overall = body["overall"]
    assert overall["orders"] > 0
    # AOV == revenue / orders
    assert overall["aov"] == pytest.approx(overall["revenue"] / overall["orders"], rel=1e-6)
    assert body["by_category"], "expected category breakdown"
    assert body["by_payment_type"], "expected payment-type breakdown"
    for row in body["by_payment_type"]:
        assert row["aov"] > 0


# ---- /metrics/delivery-sla --------------------------------------------------
def test_delivery_sla(client):
    r = client.get("/metrics/delivery-sla")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["delivered_items"] > 0
    assert 0 <= body["overall"]["on_time_pct"] <= 100
    assert body["by_state"], "expected per-state rows"
    for row in body["by_state"]:
        if row["on_time_pct"] is not None:
            assert 0 <= row["on_time_pct"] <= 100


# ---- /metrics/sellers/scorecard ---------------------------------------------
def test_seller_scorecard(client):
    r = client.get("/metrics/sellers/scorecard", params={"limit": 10})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 10
    revs = [row["revenue"] for row in rows]
    assert revs == sorted(revs, reverse=True)
    for row in rows:
        if row["avg_review_score"] is not None:
            assert 1 <= row["avg_review_score"] <= 5


# ---- /metrics/repeat-customers ----------------------------------------------
def test_repeat_customers(client):
    r = client.get("/metrics/repeat-customers")
    assert r.status_code == 200
    body = r.json()
    assert body["total_customers"] > 0
    assert 0 <= body["repeat_customers"] <= body["total_customers"]
    assert 0 <= body["repeat_rate_pct"] <= 100
    assert 0 <= body["repeat_revenue_share_pct"] <= 100
    assert body["repeat_revenue"] <= body["total_revenue"] + 1e-6
