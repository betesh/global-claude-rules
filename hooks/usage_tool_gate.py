#!/usr/bin/env python3
"""Deny a tool call before it runs, once too little budget remains for another
request.

Registered by install-hooks.sh as a PreToolUse hook. usage_gate.py
(UserPromptSubmit) only checks the fitted estimate once per prompt, but a
prompt that starts safely below GATE_AT_PCT can dispatch many tool calls before
its next check — each one triggering its own request that resends the whole
conversation (usage/notes.md: cache-read of prior context is ~98% of a
window's tokens) — so the estimate can cross GATE_AT_PCT mid-flight and the
next prompt-level check only comes after it already has. This fires before
every individual tool call and can catch that gap.

It fires once per tool_use block, but several blocks issued in parallel share
one requestId in the transcript — confirmed by tracing a live three-call
parallel batch, where all three carried the same requestId as siblings of one
assistant message. So this must not decrement a per-firing counter: it
recomputes calls-remaining from the transcript fresh on every firing, which is
why sibling calls in one batch always reach the same decision instead of three
independently discounted ones.

Every tool call is gated, not a subset of "expensive" ones: the dominant cost
of the *next* request is re-reading the whole accumulated conversation
regardless of which tool just ran (usage/notes.md), so no call is cheaper to
allow through than another.

Exit codes / stdout mirror the harness's PreToolUse contract: JSON on stdout
with hookSpecificOutput.permissionDecision selects the decision; a crash here
must never be able to block a tool call, so any exception exits 0 with none.
"""

import json
import os
import sys

import usage_common as uc

# Calls-remaining must clear this before a firing stops denying. Measured once
# (usage/notes.md): fired with single-digit calls_remaining, ahead of where
# usage_gate.py would have caught it — the gap was dominated by concurrent
# sessions' spend against the shared window, not this session's own context
# growth.
MARGIN_CALLS = float(os.environ.get("CLAUDE_TOOL_GATE_MARGIN_CALLS", "5"))


def deny_reason(state, transcript):
    """Why this tool call must not run, or None to let it through.

    Mirrors usage_gate.py's own gate_reason: blocks only when a measured slope
    stands behind the estimate (two or more readings) and the renewal it would
    wait for is a time the log actually knows — an unmeasured or unbounded
    refusal is worse than letting a request through on a bad guess.
    """
    estimate, per_pct, backing = state["estimate"], state["per_pct"], state["backing"]
    if estimate is None or backing < 2 or not per_pct:
        return None
    if not (state["renews"] > uc.now):
        return None

    remaining_tokens = (uc.GATE_AT_PCT - estimate) * per_pct
    if remaining_tokens <= 0:
        return f"the window is already ~{min(estimate, 100):.0f}% spent", state["renews"]

    if not transcript:
        return None
    carry = uc.session_carry(transcript)
    if not carry:
        return None
    context = carry[0]
    if not context:
        return None

    # An upper bound, not exact: context only grows from here, so the true
    # calls-remaining before GATE_AT_PCT is somewhat lower than this ratio.
    calls_remaining = remaining_tokens / context
    if calls_remaining >= MARGIN_CALLS:
        return None
    return (
        f"~{calls_remaining:.1f} calls of budget left ({remaining_tokens:,.0f} tokens at "
        f"~{context:,} tokens/call, {backing} readings)",
        state["renews"],
    )


def main():
    payload = uc.hook_payload()
    transcript = payload.get("transcript_path")

    events = uc.read_events()
    state = uc.window_state(events)

    reason = deny_reason(state, transcript)
    if not reason:
        return

    why, until = reason
    message = (
        f"Credit is nearly out: {why}. Denying this tool call rather than let it spend more. "
        f"Sleep in the foreground until the window renews at {uc.stamp(until)} "
        f"({uc.duration(until - uc.now)} from now), per rules/usage-limits-and-context.md — do "
        "not retry this call, and do not make further tool calls until then."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }
    }))


try:
    main()
except Exception:  # a bug here must never be able to block a tool call
    sys.exit(0)
