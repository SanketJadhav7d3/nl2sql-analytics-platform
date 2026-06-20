"""HTTP layer for /metrics/*. Routes only validate/shape input and delegate to
the service layer; no SQL or business logic lives here."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from ..db import get_conn
from ..deps import authorized
from ..services import metrics as svc
from ..schemas import (
    AovResponse,
    CategoryPerformance,
    DeliverySlaResponse,
    RepeatCustomersResponse,
    RevenueResponse,
    SellerScore,
)

# Any authenticated role (viewer/analyst/admin) may read metrics; the dependency
# also writes an audit row for every access.
router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(authorized("viewer", "analyst", "admin"))],
)


@router.get("/revenue", response_model=RevenueResponse)
def get_revenue(
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    conn: Connection = Depends(get_conn),
) -> RevenueResponse:
    points = svc.revenue_trend(conn, granularity, date_from, date_to)
    return RevenueResponse(
        granularity=granularity, date_from=date_from, date_to=date_to, points=points
    )


@router.get("/categories/top", response_model=list[CategoryPerformance])
def get_top_categories(
    limit: int = Query(10, ge=1, le=100),
    conn: Connection = Depends(get_conn),
) -> list[CategoryPerformance]:
    return svc.top_categories(conn, limit)


@router.get("/aov", response_model=AovResponse)
def get_aov(conn: Connection = Depends(get_conn)) -> AovResponse:
    return AovResponse(**svc.aov(conn))


@router.get("/delivery-sla", response_model=DeliverySlaResponse)
def get_delivery_sla(conn: Connection = Depends(get_conn)) -> DeliverySlaResponse:
    return DeliverySlaResponse(**svc.delivery_sla(conn))


@router.get("/sellers/scorecard", response_model=list[SellerScore])
def get_seller_scorecard(
    limit: int = Query(20, ge=1, le=100),
    conn: Connection = Depends(get_conn),
) -> list[SellerScore]:
    return svc.seller_scorecard(conn, limit)


@router.get("/repeat-customers", response_model=RepeatCustomersResponse)
def get_repeat_customers(
    conn: Connection = Depends(get_conn),
) -> RepeatCustomersResponse:
    return RepeatCustomersResponse(**svc.repeat_customers(conn))
