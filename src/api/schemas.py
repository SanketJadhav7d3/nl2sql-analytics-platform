"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


# ---- auth -------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ---- admin / users ----------------------------------------------------------
class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Literal["viewer", "analyst", "admin"]


class UpdateUserRequest(BaseModel):
    role: Literal["viewer", "analyst", "admin"] | None = None
    is_active: bool | None = None


class AuditEntry(BaseModel):
    id: int
    username: str | None = None
    role: str | None = None
    action: str
    detail: str | None = None
    status: str
    created_at: datetime


# ---- /query -----------------------------------------------------------------
class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    sql: str
    row_count: int
    rows: list[dict[str, Any]]


# ---- /nl-query --------------------------------------------------------------
class NLQueryRequest(BaseModel):
    question: str


class NLQueryResponse(BaseModel):
    question: str
    sql: str
    row_count: int
    rows: list[dict[str, Any]]


# ---- /metrics/revenue -------------------------------------------------------
class RevenuePoint(BaseModel):
    period: date
    revenue: float
    orders: int
    running_total_revenue: float
    mom_growth_pct: float | None = None


class RevenueResponse(BaseModel):
    granularity: str
    date_from: date | None = None
    date_to: date | None = None
    points: list[RevenuePoint]


# ---- /metrics/categories/top ------------------------------------------------
class CategoryPerformance(BaseModel):
    revenue_rank: int
    category: str
    revenue: float
    items_sold: int
    orders: int
    avg_review_score: float | None = None
    revenue_share_pct: float


# ---- /metrics/aov -----------------------------------------------------------
class AovOverall(BaseModel):
    revenue: float
    orders: int
    aov: float


class AovByCategory(BaseModel):
    category: str
    aov: float
    orders: int
    revenue: float


class AovByPaymentType(BaseModel):
    payment_type: str
    aov: float
    orders: int
    revenue: float


class AovResponse(BaseModel):
    overall: AovOverall
    by_category: list[AovByCategory]
    by_payment_type: list[AovByPaymentType]


# ---- /metrics/delivery-sla --------------------------------------------------
class DeliverySlaState(BaseModel):
    customer_state: str
    delivered_items: int
    avg_delivery_days: float | None = None
    on_time_pct: float | None = None


class DeliverySlaOverall(BaseModel):
    delivered_items: int
    avg_delivery_days: float | None = None
    on_time_pct: float | None = None


class DeliverySlaResponse(BaseModel):
    overall: DeliverySlaOverall
    by_state: list[DeliverySlaState]


# ---- /metrics/sellers/scorecard ---------------------------------------------
class SellerScore(BaseModel):
    revenue_rank: int
    seller_id: str
    seller_state: str | None = None
    revenue: float
    items_sold: int
    orders: int
    avg_review_score: float | None = None
    avg_delivery_days: float | None = None


# ---- /metrics/repeat-customers ----------------------------------------------
class RepeatCustomersResponse(BaseModel):
    total_customers: int
    repeat_customers: int
    repeat_rate_pct: float
    total_revenue: float
    repeat_revenue: float
    repeat_revenue_share_pct: float
