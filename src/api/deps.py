"""Authentication + RBAC dependencies.

`get_current_user` resolves the bearer token to an active user. `authorized(*roles)`
is the single RBAC gate used by every protected router: it records an audit row
for the access decision (allowed AND denied) before enforcing the role.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import service
from .auth.security import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    user = service.get_user(payload["sub"])
    if not user or not user["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


def authorized(*roles: str) -> Callable:
    """Dependency factory: allow only `roles`, auditing every decision."""

    def dependency(
        request: Request,
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        allowed = user["role"] in roles
        service.record_audit(
            username=user["username"],
            role=user["role"],
            action=f"{request.method} {request.url.path}",
            detail=str(request.query_params) or None,
            status="allowed" if allowed else "denied",
        )
        if not allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"role '{user['role']}' not permitted (requires one of {roles})",
            )
        return user

    return dependency
