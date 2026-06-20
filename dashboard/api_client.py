"""Thin HTTP client the Streamlit dashboard uses to talk to the FastAPI backend."""
from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    """Carries a human-readable message extracted from an API error response."""


class ApiClient:
    def __init__(self, base: str = API_BASE, token: str | None = None):
        self.base = base.rstrip("/")
        self.token = token

    # -- auth ---------------------------------------------------------------
    def login(self, username: str, password: str) -> dict[str, Any]:
        r = httpx.post(f"{self.base}/auth/login",
                       json={"username": username, "password": password}, timeout=30)
        if r.status_code != 200:
            raise ApiError(self._detail(r, "login failed"))
        return r.json()

    # -- generic ------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def get(self, path: str, params: dict | None = None) -> Any:
        r = httpx.get(f"{self.base}{path}", headers=self._headers(),
                      params=params, timeout=60)
        if r.status_code != 200:
            raise ApiError(self._detail(r, f"GET {path} failed"))
        return r.json()

    def post(self, path: str, json: dict) -> tuple[int, Any]:
        """Returns (status_code, body) so callers can show guardrail messages."""
        r = httpx.post(f"{self.base}{path}", headers=self._headers(),
                       json=json, timeout=120)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = {"detail": r.text}
        return r.status_code, body

    @staticmethod
    def _detail(resp: httpx.Response, fallback: str) -> str:
        try:
            return resp.json().get("detail", fallback)
        except Exception:  # noqa: BLE001
            return f"{fallback} ({resp.status_code})"
