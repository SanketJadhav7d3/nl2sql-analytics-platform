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

import mlflow
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

    @mlflow.trace(name="gemini.generate_sql", span_type="LLM")
    def generate_sql(self, question: str, schema_prompt: str) -> str:
        mlflow.update_current_trace(tags={"provider": "gemini", "model": self.model})
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
        sql = parsed.sql if isinstance(parsed, _SQLOut) else json.loads(resp.text)["sql"]
        mlflow.update_current_trace(tags={"sql": sql})
        return sql


class GroqAdapter(LLMAdapter):
    """Fallback provider — Groq exposes an OpenAI-compatible API, called via
    the `openai` SDK pointed at Groq's base URL. Used automatically when
    Gemini errors (e.g. quota exhausted) and a GROQ_API_KEY is configured."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI  # imported lazily so the package isn't required unless used

        self.model = model or settings.groq_model
        self.client = OpenAI(api_key=api_key or settings.groq_api_key, base_url="https://api.groq.com/openai/v1")

    @mlflow.trace(name="groq.generate_sql", span_type="LLM")
    def generate_sql(self, question: str, schema_prompt: str) -> str:
        from ..llm_util import groq_call_with_retry

        used_model = self.model

        def request(model: str) -> str:
            nonlocal used_model
            used_model = model
            resp = self.client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + '\nRespond with JSON: {"sql": "..."}'},
                    {"role": "user", "content": f"{schema_prompt}\n\nQuestion: {question}"},
                ],
            )
            return json.loads(resp.choices[0].message.content)["sql"]

        sql = groq_call_with_retry(request, model=self.model, fallback_model=settings.groq_fallback_model)
        mlflow.update_current_trace(tags={"provider": "groq", "model": used_model, "sql": sql})
        return sql


class EchoAdapter(LLMAdapter):
    """Offline fallback. Returns a fixed safe query regardless of the question —
    useful for demoing the endpoint and guardrails without an API key."""

    def generate_sql(self, question: str, schema_prompt: str) -> str:
        return (
            "SELECT category, revenue, revenue_rank "
            "FROM vw_category_performance ORDER BY revenue_rank LIMIT 10"
        )


class FallbackAdapter(LLMAdapter):
    """Tries `primary`; on any error (e.g. Gemini quota exhausted), retries
    with `secondary` instead of failing the request outright."""

    def __init__(self, primary: LLMAdapter, secondary: LLMAdapter):
        self.primary = primary
        self.secondary = secondary

    @mlflow.trace(name="nl_query.generate_sql", span_type="CHAIN")
    def generate_sql(self, question: str, schema_prompt: str) -> str:
        mlflow.update_current_trace(tags={"question": question})
        try:
            sql = self.primary.generate_sql(question, schema_prompt)
            mlflow.update_current_trace(tags={"fell_back": "false"})
            return sql
        except Exception as exc:  # noqa: BLE001  (deliberately broad — any primary failure falls back)
            mlflow.update_current_trace(tags={"fell_back": "true", "primary_error": str(exc)})
            return self.secondary.generate_sql(question, schema_prompt)


@lru_cache(maxsize=1)
def get_adapter() -> LLMAdapter:
    """FastAPI dependency. Cached so the SDK client(s) are built once."""
    if settings.llm_provider == "echo":
        return EchoAdapter()
    if settings.groq_api_key:
        return FallbackAdapter(GeminiAdapter(), GroqAdapter())
    return GeminiAdapter()
