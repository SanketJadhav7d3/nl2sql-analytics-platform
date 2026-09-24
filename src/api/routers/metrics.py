"""HTTP layer for /metrics/*. Routes only validate/shape input and delegate to
the service layer; no SQL or business logic lives here."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from ..datasets import analytics_schema, raw_schema
from ..db import get_conn
from ..deps import authorized
from ..schemas import (
    AovResponse,
    CategoryPerformance,
    DeliverySlaResponse,
    RepeatCustomersResponse,
    RevenueResponse,
    SellerScore,
)
from ..services import metrics as svc

# Any authenticated role (viewer/analyst/admin) may read metrics; the dependency
# also writes an audit row for every access.
router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(authorized("viewer", "analyst", "admin"))],
)

DatasetParam = Literal["olist", "us"]


@router.get("/revenue", response_model=RevenueResponse)
def get_revenue(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    dataset: DatasetParam = "olist",
    conn: Connection = Depends(get_conn),
) -> RevenueResponse:
    points = svc.revenue_trend(conn, granularity, date_from, date_to, analytics_schema(dataset))
    return RevenueResponse(
        granularity=granularity, date_from=date_from, date_to=date_to, points=points
    )


@router.get("/categories/top", response_model=list[CategoryPerformance])
def get_top_categories(
    limit: int = Query(10, ge=1, le=100),
    dataset: DatasetParam = "olist",
    conn: Connection = Depends(get_conn),
) -> list[CategoryPerformance]:
    return svc.top_categories(conn, limit, analytics_schema(dataset))


@router.get("/aov", response_model=AovResponse)
def get_aov(dataset: DatasetParam = "olist", conn: Connection = Depends(get_conn)) -> AovResponse:
    return AovResponse(**svc.aov(conn, analytics_schema(dataset), raw_schema(dataset)))


@router.get("/delivery-sla", response_model=DeliverySlaResponse)
def get_delivery_sla(dataset: DatasetParam = "olist", conn: Connection = Depends(get_conn)) -> DeliverySlaResponse:
    return DeliverySlaResponse(**svc.delivery_sla(conn, analytics_schema(dataset)))


@router.get("/sellers/scorecard", response_model=list[SellerScore])
def get_seller_scorecard(
    limit: int = Query(20, ge=1, le=100),
    dataset: DatasetParam = "olist",
    conn: Connection = Depends(get_conn),
) -> list[SellerScore]:
    return svc.seller_scorecard(conn, limit, analytics_schema(dataset))


@router.get("/repeat-customers", response_model=RepeatCustomersResponse)
def get_repeat_customers(
    dataset: DatasetParam = "olist",
    conn: Connection = Depends(get_conn),
) -> RepeatCustomersResponse:
    return RepeatCustomersResponse(**svc.repeat_customers(conn, analytics_schema(dataset)))
