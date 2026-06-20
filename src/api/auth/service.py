"""User and audit-log persistence.

Writes use `engine.begin()` (their own short transaction) so they commit
independently of the per-request read-only connection.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..db import engine
from .security import hash_password, verify_password

VALID_ROLES = ("viewer", "analyst", "admin")


# ---- audit ----------------------------------------------------------------
def record_audit(
    username: str | None,
    role: str | None,
    action: str,
    status: str,
    detail: str | None = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO app.audit_log (username, role, action, detail, status)
                VALUES (:username, :role, :action, :detail, :status)
                """
            ),
            {"username": username, "role": role, "action": action,
             "detail": detail, "status": status},
        )


def list_audit(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, username, role, action, detail, status, created_at
                FROM app.audit_log
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings()
        return [dict(r) for r in rows]


# ---- users ----------------------------------------------------------------
def get_user(username: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, username, hashed_password, role, is_active, created_at
                FROM app.users WHERE username = :u
                """
            ),
            {"u": username},
        ).mappings().first()
        return dict(row) if row else None


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    user = get_user(username)
    if not user or not user["is_active"]:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def list_users() -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, username, role, is_active, created_at
                FROM app.users ORDER BY id
                """
            )
        ).mappings()
        return [dict(r) for r in rows]


def create_user(username: str, password: str, role: str) -> dict[str, Any]:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO app.users (username, hashed_password, role)
                VALUES (:u, :p, :r)
                RETURNING id, username, role, is_active, created_at
                """
            ),
            {"u": username, "p": hash_password(password), "r": role},
        ).mappings().one()
        return dict(row)


def update_user(user_id: int, role: str | None = None,
                is_active: bool | None = None) -> dict[str, Any] | None:
    if role is not None and role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role!r}")
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE app.users
                SET role      = COALESCE(:role, role),
                    is_active = COALESCE(:is_active, is_active)
                WHERE id = :id
                RETURNING id, username, role, is_active, created_at
                """
            ),
            {"id": user_id, "role": role, "is_active": is_active},
        ).mappings().first()
        return dict(row) if row else None


def delete_user(user_id: int) -> bool:
    with engine.begin() as conn:
        res = conn.execute(
            text("DELETE FROM app.users WHERE id = :id"), {"id": user_id}
        )
        return res.rowcount > 0
