"""Admin CLI for the auth layer.

    python -m src.api.auth.manage init
        Create the app schema + read-only role, and seed a default admin
        (admin / admin123) if no admin exists.

    python -m src.api.auth.manage create-user <username> <password> <role>
        Create a user (role = viewer | analyst | admin).
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

from ..db import engine
from . import service

SQL_FILE = Path(__file__).resolve().parents[3] / "sql" / "03_app_schema.sql"
DEFAULT_ADMIN = ("admin", "admin123")


def init() -> None:
    print(f"Applying {SQL_FILE.name} ...")
    with engine.begin() as conn:
        conn.execute(text(SQL_FILE.read_text(encoding="utf-8")))
    # seed admin if none
    with engine.connect() as conn:
        has_admin = conn.execute(
            text("SELECT 1 FROM app.users WHERE role = 'admin' LIMIT 1")
        ).first()
    if not has_admin:
        service.create_user(*DEFAULT_ADMIN, role="admin")
        print(f"Seeded default admin: {DEFAULT_ADMIN[0]} / {DEFAULT_ADMIN[1]}")
    else:
        print("Admin already exists; not seeding.")
    print("Auth layer ready.")


def create_user(username: str, password: str, role: str) -> None:
    u = service.create_user(username, password, role)
    print(f"Created user #{u['id']}: {u['username']} ({u['role']})")


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "init":
        init()
        return 0
    if argv[0] == "create-user" and len(argv) == 4:
        create_user(argv[1], argv[2], argv[3])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
