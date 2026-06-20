"""/admin/* — admin-only user management and audit-log access."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import service
from ..deps import authorized
from ..schemas import (
    AuditEntry,
    CreateUserRequest,
    UpdateUserRequest,
    UserOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(user: dict[str, Any] = Depends(authorized("admin"))):
    return service.list_users()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    user: dict[str, Any] = Depends(authorized("admin")),
):
    try:
        created = service.create_user(body.username, body.password, body.role)
    except Exception as exc:  # noqa: BLE001 (unique violation, etc.)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"could not create user: {exc}")
    service.record_audit(user["username"], user["role"], "admin:create_user",
                         status="allowed", detail=f"{body.username} ({body.role})")
    return created


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    user: dict[str, Any] = Depends(authorized("admin")),
):
    updated = service.update_user(user_id, role=body.role, is_active=body.is_active)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    service.record_audit(user["username"], user["role"], "admin:update_user",
                         status="allowed", detail=f"id={user_id} {body.model_dump()}")
    return updated


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, user: dict[str, Any] = Depends(authorized("admin"))):
    if not service.delete_user(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    service.record_audit(user["username"], user["role"], "admin:delete_user",
                         status="allowed", detail=f"id={user_id}")


@router.get("/audit-log", response_model=list[AuditEntry])
def audit_log(
    limit: int = 100,
    user: dict[str, Any] = Depends(authorized("admin")),
):
    return service.list_audit(limit)
