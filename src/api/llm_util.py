"""Shared retry/fallback helper for Groq calls.

Groq enforces per-model tokens-per-minute budgets, so a 429 on the primary
model doesn't mean Groq itself is unavailable — a lighter model often still
has headroom. Used by both the NL-to-SQL adapter and the Story agent.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_RETRY_SECONDS_RE = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)


def groq_call_with_retry(request: Callable[[str], T], *, model: str, fallback_model: str | None) -> T:
    """Calls `request(model)`. On a 429 (tokens-per-minute rate limit): waits
    the server-suggested backoff (capped at 15s) and retries the same model
    once, then falls back to `fallback_model` if still rate-limited. Any
    other exception propagates immediately."""
    from openai import RateLimitError

    try:
        return request(model)
    except RateLimitError as exc:
        wait = _extract_retry_seconds(str(exc))
        if wait is not None and wait <= 15:
            time.sleep(wait)
            try:
                return request(model)
            except RateLimitError:
                pass
        if fallback_model and fallback_model != model:
            return request(fallback_model)
        raise


def _extract_retry_seconds(message: str) -> float | None:
    m = _RETRY_SECONDS_RE.search(message)
    return float(m.group(1)) + 0.5 if m else None
