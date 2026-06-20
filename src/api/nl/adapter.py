"""Swappable LLM adapter for the NL-to-SQL assistant.

The provider is hidden behind `LLMAdapter` so it can be swapped without touching
the service or guardrails. `GeminiAdapter` is the real implementation (uses
Google's `google-genai` SDK with a structured JSON schema so the model returns a
clean `{"sql": ...}` object, not prose or markdown fences). `EchoAdapter` runs
offline for demos/tests without an API key.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache

from pydantic import BaseModel

from ..config import settings

SYSTEM_PROMPT = (
    "You translate a business question into ONE read-only PostgreSQL SELECT "
    "statement against the provided `analytics` schema.\n"
    "Rules you MUST follow:\n"
    "- Output exactly one statement; it must start with SELECT or WITH.\n"
    "- Never write/modify data (no INSERT/UPDATE/DELETE/DDL) and no semicolons.\n"
    "- Only reference the tables/views listed in the schema; the search_path is "
    "already set to `analytics`, so table names need no schema prefix.\n"
    "- Always include a LIMIT.\n"
    "- Return only the SQL via the structured output; no explanation."
)

class _SQLOut(BaseModel):
    """Structured-output schema: forces a single {"sql": "..."} object."""
    sql: str


class LLMAdapter(ABC):
    @abstractmethod
    def generate_sql(self, question: str, schema_prompt: str) -> str:
        """Return a SQL string for the question. May be unsafe — the caller
        runs it through the guardrails before execution."""


class GeminiAdapter(LLMAdapter):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        from google import genai  # imported lazily so the package isn't required offline

        self.model = model or settings.llm_model
        key = api_key or settings.gemini_api_key
        # No key here -> SDK reads GEMINI_API_KEY / GOOGLE_API_KEY from the env.
        self.client = genai.Client(api_key=key) if key else genai.Client()

    def generate_sql(self, question: str, schema_prompt: str) -> str:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=f"{schema_prompt}\n\nQuestion: {question}",
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": _SQLOut,
            },
        )
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, _SQLOut):
            return parsed.sql
        return json.loads(resp.text)["sql"]


class EchoAdapter(LLMAdapter):
    """Offline fallback. Returns a fixed safe query regardless of the question —
    useful for demoing the endpoint and guardrails without an API key."""

    def generate_sql(self, question: str, schema_prompt: str) -> str:
        return (
            "SELECT category, revenue, revenue_rank "
            "FROM vw_category_performance ORDER BY revenue_rank LIMIT 10"
        )


@lru_cache(maxsize=1)
def get_adapter() -> LLMAdapter:
    """FastAPI dependency. Cached so the SDK client is built once."""
    if settings.llm_provider == "echo":
        return EchoAdapter()
    return GeminiAdapter()
