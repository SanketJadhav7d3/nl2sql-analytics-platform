"""/query — analyst+admin run vetted read-only SQL against the analytics schema."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import service
from ..deps import authorized
from ..schemas import QueryRequest, QueryResponse
from ..sql_guard import GuardrailError, run_read_only

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def run_query(
    body: QueryRequest,
    user: dict[str, Any] = Depends(authorized("analyst", "admin")),
) -> QueryResponse:
    try:
        rows = run_read_only(body.sql)
    except GuardrailError as exc:
        service.record_audit(user["username"], user["role"], "query",
                             status="denied", detail=f"{body.sql} -> {exc}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"guardrail: {exc}")
    except Exception as exc:  # noqa: BLE001  (e.g. permission denied from RO role)
        service.record_audit(user["username"], user["role"], "query",
                             status="error", detail=f"{body.sql} -> {exc}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "query failed")

    service.record_audit(user["username"], user["role"], "query",
                         status="allowed", detail=body.sql)
    return QueryResponse(sql=body.sql, row_count=len(rows), rows=rows)
