"""/nl-query — natural-language question -> guarded SQL -> rows (analyst+admin)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import service
from ..deps import authorized
from ..nl.adapter import LLMAdapter, get_adapter
from ..nl.service import nl_query
from ..schemas import NLQueryRequest, NLQueryResponse
from ..sql_guard import GuardrailError

router = APIRouter(tags=["nl-query"])


@router.post("/nl-query", response_model=NLQueryResponse)
def post_nl_query(
    body: NLQueryRequest,
    user: dict[str, Any] = Depends(authorized("analyst", "admin")),
    adapter: LLMAdapter = Depends(get_adapter),
) -> NLQueryResponse:
    try:
        result = nl_query(body.question, adapter)
    except GuardrailError as exc:
        service.record_audit(user["username"], user["role"], "nl-query",
                             status="denied", detail=f"{body.question} -> {exc}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"guardrail: {exc}")
    except Exception as exc:  # noqa: BLE001  (LLM error or RO permission denial)
        service.record_audit(user["username"], user["role"], "nl-query",
                             status="error", detail=f"{body.question} -> {exc}")
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "could not answer question")

    service.record_audit(user["username"], user["role"], "nl-query",
                         status="allowed",
                         detail=f"{body.question} => {result['sql']}")
    return NLQueryResponse(**result)
