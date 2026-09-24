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
        with mlflow.start_span(name="story_turn", span_type="AGENT") as span:
            span.set_attributes({
                "message": body.message, "history_len": len(history),
                "user": user["username"], "dataset": body.dataset,
            })
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
                span.set_attributes({"status": status})
                service.record_audit(user["username"], user["role"], "story", status=status, detail=detail)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
