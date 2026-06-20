"""Login endpoint — exchanges username/password for a JWT."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..auth import service
from ..auth.security import create_access_token
from ..schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    user = service.authenticate(body.username, body.password)
    if user is None:
        service.record_audit(body.username, None, "POST /auth/login",
                             status="denied", detail="bad credentials")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    service.record_audit(user["username"], user["role"], "POST /auth/login",
                         status="allowed")
    token = create_access_token(user["username"], user["role"])
    return TokenResponse(access_token=token, role=user["role"])
