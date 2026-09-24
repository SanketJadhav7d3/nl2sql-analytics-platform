"""A tiny graph executor for the Story agent, with provider recovery.

The agent is a three-node state machine:

        plan ──calls?──▶ act ──▶ plan          (investigate)
          │  no calls
          └────────────▶ DONE                  (model wrapped up on its own)
        plan (step ceiling reached) ──▶ finalize ──▶ DONE

  plan      one LLM call. May narrate, may ask for SQL, may do both.
  act       run the proposed SQL through the normal guardrail, capped small,
            and append the result to the transcript.
  finalize  one LLM call with the tool REMOVED, so the model cannot query and
            must produce prose. Guarantees a turn always ends in narration.

Why a graph rather than the previous `for` loop
-----------------------------------------------
The loop kept its state in the provider's own message objects, so a failure
mid-turn could only be answered by aborting: there was no way to hand what had
been accumulated to a different provider. Here the canonical state is our own
provider-neutral step dicts (`StoryState.transcript`), and every node is a pure
function of that state. So the executor can snapshot the state before a node,
and on a provider failure restore the snapshot, switch provider, and re-run
*that same node* — the investigation continues from where it was instead of
being thrown away.

Rollback contract
-----------------
A node must not yield any event before its fallible work has completed. The
executor enforces the safe half of this: if a node has already emitted when it
fails, the failure is terminal for the turn rather than being rewound, because
those events are already on the client's transcript and cannot be unsaid. The
`plan` and `finalize` nodes obey the contract naturally (LLM call first, then
yield); `act` yields first but only performs database work, which reports
errors as ordinary tool results rather than raising.

The cost of recovery, stated plainly: a turn can end up part-narrated by one
model and part by another. The previous design refused that on the grounds
that a silent voice change is a worse failure than an honest error. The
compromise here is that the switch is never silent — a `provider_switch` event
is emitted so the UI can say so.
"""
from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .providers import Provider

# Nodes
PLAN = "plan"
ACT = "act"
FINALIZE = "finalize"
DONE = None


class ProviderError(Exception):
    """A provider call failed (quota, rate limit, server spike, bad response).

    Raised by the executor around `Provider.propose`, and the only exception it
    will attempt to recover from.
    """

    def __init__(self, provider: str, cause: BaseException):
        super().__init__(f"{provider}: {cause}")
        self.provider = provider
        self.cause = cause


@dataclass
class StoryState:
    """Everything a node needs, and nothing provider-specific.

    `transcript` is the conversation so far in our own step format: prior turns
    from the client, this turn's user message, and every narration/tool step
    produced so far. It is what each provider replays into its native format.
    """

    dataset: str
    system_instruction: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    pending_sql: list[str] = field(default_factory=list)
    steps_used: int = 0
    max_steps: int = 6
    narrated: bool = False
    next_node: str | None = PLAN

    def snapshot(self) -> dict[str, Any]:
        return {
            "transcript": copy.deepcopy(self.transcript),
            "pending_sql": list(self.pending_sql),
            "steps_used": self.steps_used,
            "narrated": self.narrated,
            "next_node": self.next_node,
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self.transcript = snap["transcript"]
        self.pending_sql = snap["pending_sql"]
        self.steps_used = snap["steps_used"]
        self.narrated = snap["narrated"]
        self.next_node = snap["next_node"]


# ---------------------------------------------------------------------------
# Nodes. Each is a generator of client events; each sets `state.next_node`.
# ---------------------------------------------------------------------------
def plan_node(state: StoryState, provider: Provider, run_sql: Callable) -> Iterator[dict]:
    """One LLM call. Fallible — and it yields nothing until the call returns,
    so the executor can rewind it cleanly."""
    if state.steps_used >= state.max_steps:
        # Out of investigation budget: stop querying and force a wrap-up.
        state.next_node = FINALIZE
        return

    state.steps_used += 1
    proposal = _call(provider, state, with_tools=True)

    if proposal.narration:
        state.narrated = True
        step = {"role": "assistant", "narration": proposal.narration,
                "sql": None, "columns": None, "rows": None}
        state.transcript.append(step)
        yield {"type": "step", **step}

    if proposal.calls:
        state.pending_sql = list(proposal.calls)
        state.next_node = ACT
    else:
        # No tool call: the model has finished investigating.
        state.next_node = DONE


def act_node(state: StoryState, provider: Provider, run_sql: Callable) -> Iterator[dict]:
    """Execute the proposed SQL. Not fallible in the recoverable sense: the
    guardrail and the database report problems as ordinary tool results, so the
    model sees what went wrong and can try something else."""
    for sql in state.pending_sql:
        yield {"type": "tool_call", "sql": sql}
        result = run_sql(sql, state.dataset)
        step = {
            "role": "assistant",
            "narration": None,
            "sql": sql,
            "columns": result.get("columns"),
            "rows": result.get("rows"),
        }
        if result.get("note"):
            step["note"] = result["note"]
        state.transcript.append(step)
        if "error" not in result:
            yield {"type": "step", **{k: v for k, v in step.items() if k != "note"}}
        else:
            # Keep the error in the transcript for the model, but don't render a
            # failed query as a result card in the UI.
            step["columns"], step["rows"] = None, None
            step["note"] = result["error"]
    state.pending_sql = []
    state.next_node = PLAN


def finalize_node(state: StoryState, provider: Provider, run_sql: Callable) -> Iterator[dict]:
    """One tool-free LLM call, so the model must answer in prose."""
    state.transcript.append({
        "role": "user",
        "narration": "Stop investigating now and give your final narration and key takeaway.",
        "sql": None, "columns": None, "rows": None,
    })
    proposal = _call(provider, state, with_tools=False)
    if proposal.narration:
        state.narrated = True
        step = {"role": "assistant", "narration": proposal.narration,
                "sql": None, "columns": None, "rows": None}
        state.transcript.append(step)
        yield {"type": "step", **step}
    state.next_node = DONE


def _call(provider: Provider, state: StoryState, *, with_tools: bool):
    """Invoke a provider, normalising every failure into ProviderError so the
    executor has exactly one thing to catch."""
    try:
        return provider.propose(state.transcript, state.system_instruction, with_tools=with_tools)
    except Exception as exc:  # noqa: BLE001  (any provider failure is recoverable)
        raise ProviderError(provider.name, exc) from exc


NODES: dict[str, Callable[..., Iterator[dict]]] = {
    PLAN: plan_node,
    ACT: act_node,
    FINALIZE: finalize_node,
}


# ---------------------------------------------------------------------------
def execute(
    state: StoryState,
    providers: list[Provider],
    run_sql: Callable,
    nodes: dict[str, Callable[..., Iterator[dict]]] | None = None,
) -> Iterator[dict]:
    """Run the graph to completion, yielding client events as they happen.

    Recovery: if a node raises ProviderError *before emitting anything*, the
    state is rolled back to the snapshot taken before that node, the next
    provider in `providers` is selected, and the same node runs again. Each
    provider is tried at most once per node; when the list is exhausted the
    turn ends with an `error` event.

    Always ends with exactly one terminal event: `done` or `error`.
    """
    nodes = nodes or NODES
    if not providers:
        yield {"type": "error", "message": "no LLM provider is configured"}
        return

    provider_ix = 0

    while state.next_node is not None:
        node_name = state.next_node
        node_fn = nodes[node_name]
        snapshot = state.snapshot()
        # Providers not yet tried for THIS node, in preference order.
        attempts = list(range(provider_ix, len(providers)))
        last_error: ProviderError | None = None

        for attempt_ix, ix in enumerate(attempts):
            provider = providers[ix]
            emitted_here = False
            try:
                for event in node_fn(state, provider, run_sql):
                    emitted_here = True
                    yield event
            except ProviderError as exc:
                last_error = exc
                if emitted_here:
                    # Part of this node already reached the client; rewinding
                    # would contradict what the user has already been shown.
                    yield {"type": "error", "message": str(exc)}
                    return
                if attempt_ix + 1 >= len(attempts):
                    break  # no provider left to try
                state.restore(snapshot)
                provider_ix = ix + 1
                nxt = providers[provider_ix]
                yield {
                    "type": "provider_switch",
                    "from": provider.name,
                    "to": nxt.name,
                    "node": node_name,
                    "message": (
                        f"{provider.name} failed ({exc.cause}); "
                        f"continuing this investigation on {nxt.name}."
                    ),
                }
                continue
            else:
                provider_ix = ix  # this provider worked; stay on it
                last_error = None
                break

        if last_error is not None:
            yield {"type": "error", "message": str(last_error)}
            return

    if not state.narrated:
        yield {
            "type": "step",
            "role": "assistant",
            "narration": "The agent didn't produce a response.",
            "sql": None, "columns": None, "rows": None,
        }
    yield {"type": "done"}
