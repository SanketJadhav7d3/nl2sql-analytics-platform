"""/story — agentic, multi-turn conversational investigation, streamed to the
client as Server-Sent Events (viewer/analyst/admin — same read-only access
level as /nl-query). Stateless: the client resends the transcript (`history`)
with each message."""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import mlflow
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..auth import service
from ..deps import authorized
from ..schemas import StoryRequest
from ..story.service import run_story_stream

router = APIRouter(tags=["story"])


@router.post("/story")
def post_story(
    body: StoryRequest,
    user: dict[str, Any] = Depends(authorized("viewer", "analyst", "admin")),
) -> StreamingResponse:
    history = [step.model_dump() for step in body.history]

    def event_stream() -> Iterator[str]:
        status = "allowed"
        detail = f"[{body.dataset}] {body.message}"
        # NOT `with mlflow.start_span(...)`. That context manager attaches the
        # span to an OpenTelemetry contextvar and detaches it on exit, but
        # Starlette consumes a sync generator one item at a time via
        # anyio.to_thread, each `next()` in a *copied* context. The token taken
        # on the first next() is therefore invalid by the last one, and exiting
        # raised "ValueError: <Token ...> was created in a different Context"
        # on every single /story request — after the client had already been
        # served, so it showed up purely as ASGI error noise that would bury
        # real failures. start_span_no_context() has an explicit lifecycle and
        # touches no contextvar, so it is safe to span across yields.
        # Trade-off: child spans (the provider calls, run_tool_sql) find no
        # active span and are recorded as their own traces rather than nested
        # under this one.
        span = mlflow.start_span_no_context(
            name="story_turn",
            span_type="AGENT",
            attributes={
                "message": body.message, "history_len": len(history),
                "user": user["username"], "dataset": body.dataset,
            },
        )
        try:
            for event in run_story_stream(body.message, history, body.dataset):
                if event.get("type") == "error":
                    status = "error"
                    detail = f"[{body.dataset}] {body.message} -> {event.get('message')}"
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001  (should be unreachable — run_story_stream catches internally)
            status = "error"
            detail = f"[{body.dataset}] {body.message} -> {exc}"
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            # Both of these must happen even if the client disconnects
            # mid-stream, which closes the generator and raises GeneratorExit
            # at the yield above.
            try:
                span.set_attributes({"status": status})
                span.end()
            except Exception:  # noqa: BLE001  (tracing must never break a response)
                pass
            service.record_audit(user["username"], user["role"], "story", status=status, detail=detail)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
