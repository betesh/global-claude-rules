#!/usr/bin/env python3
"""Decide whether a prompt is worth sending, before it is sent.

Invoked by usage-gate.sh with REPO_DIR set, on every UserPromptSubmit. The
SessionStart report (usage_report.py) runs once, before a session has spent
anything, so nothing watches the window while it actually drains. This runs on
every prompt, off the same fitted estimate, and is the only place a spent
window can be noticed for free — once the model is invoked the request is
already paid for, so a rule telling it to stop cannot un-spend one.

Exit codes are the whole interface:

  2  credit is gone, or this session should clear before spending the window;
     the harness drops the prompt and shows our stderr
  0  send it — stdout, if any, becomes context for this turn

Only a deliberate 2 blocks. Any other failure — a crash, a missing python, a
malformed log — exits 0, because a bug in accounting must never be able to
lock someone out of their own session.
"""

import argparse
import os
import sys

import usage_common as uc


def parse_args():
    parser = argparse.ArgumentParser(description="Gate a prompt on the shared credit window.")
    parser.add_argument("--session", help="session id to tag anything this run appends to the log")
    parser.add_argument("--transcript", help="transcript to weigh instead of the one on stdin")
    return parser.parse_args()


def gate_reason(state):
    """Why this request must not be sent, or None to let it through.

    The fitted estimate is the only ground, and it is not a trustworthy one. It
    has been wrong by a factor of two in this repo's own measurements, and
    refusing on a bad one idles every agent on the machine until the window
    turns over, which is the more expensive mistake because nobody notices it.
    So it blocks only when a measured slope stands behind it (two or more
    readings) and the renewal it would wait for is a time the log actually knows.
    """
    estimate, last = state["estimate"], state["last"]
    if estimate is None or estimate < uc.GATE_AT_PCT or state["backing"] < 2:
        return None
    if not (state["renews"] > uc.now):
        return None
    return (
        f"the window is ~{min(estimate, 100):.0f}% spent — {state['per_pct']:,.0f} tokens/% "
        f"fitted on {state['backing']} readings, last the {last['pct']}% at {uc.stamp(last['_t'])}",
        state["renews"],
    )


def carried_reason(events, state, session_id, transcript):
    """Why this session should clear before spending the window, or None.

    Both conditions are required. A session that merely grew large during this
    window carries nothing across the boundary: everything in it was paid for at
    cache-write prices already, and clearing saves only the re-reads it has left.
    The saving is the history times the requests still to come, which is why the
    boundary is the moment worth interrupting and no other moment is.
    """
    if os.environ.get("CLAUDE_CARRIED_CONTEXT_OK") == "1" or not transcript:
        return None
    # A start the log only guessed is this session's own start time, so every
    # session looks older than the window and every one of them would be blocked.
    if state["opened"]:
        return None
    carry = uc.session_carry(transcript, state["window_start"])
    if not carry:
        return None
    context, first, requests = carry
    if first >= state["window_start"] or context < uc.CARRY_AT:
        return None
    # Re-submitting is the acknowledgement. Nobody is locked out of their own
    # session by a threshold that turns out to be wrong.
    for event in events:
        if (event.get("kind") == "carried-context" and event.get("session") == session_id
                and event["_t"] >= state["window_start"]):
            return None

    hours = max((uc.now - state["window_start"]).total_seconds() / 3600, 0.01)
    per_hour = requests / hours
    remaining = max((state["renews"] - uc.now).total_seconds() / 3600, 0)
    projected = context * per_hour * remaining
    cost = f"~{projected / 1e6:.1f}M tokens" if projected else "nothing further"
    if state["per_pct"]:
        cost += f", about {projected / state['per_pct']:.0f}% of the window"
    return (
        f"this session predates the window and is holding {context:,} tokens of history. "
        f"Every request re-sends all of it: at {per_hour:.0f} requests/hour over the "
        f"{uc.duration(state['renews'] - uc.now)} left, continuing here spends {cost} on history alone."
    )


def main():
    args = parse_args()
    payload = uc.hook_payload()
    session_id = args.session or payload.get("session_id") or None
    transcript = args.transcript or payload.get("transcript_path") or None

    events = uc.read_events()
    state = uc.window_state(events)
    if state["unlogged"]:
        uc.log_boundary(session_id, state["window_start"])

    reason = gate_reason(state)
    if reason:
        why, until = reason
        print(
            f"Credit is out: {why}. Not sending this request. The window renews at "
            f"{uc.stamp(until)}, {uc.duration(until - uc.now)} from now — wait until then, or set "
            f"CLAUDE_USAGE_GATE_PCT above {uc.GATE_AT_PCT:.0f} to override.",
            file=sys.stderr,
        )
        sys.exit(2)

    carried = carried_reason(events, state, session_id, transcript)
    if carried:
        uc.append_event(session_id, {"kind": "carried-context"})
        print(
            f"{carried} Use /clear if the next task does not depend on this conversation, or "
            "/compact if the work must continue here. To keep it anyway, send the prompt again — "
            "this asks once per window — or set CLAUDE_CARRIED_CONTEXT_OK=1 for a run that "
            "cannot answer a prompt.",
            file=sys.stderr,
        )
        sys.exit(2)

    if state["estimate"] is not None:
        print(
            f"credit ~{min(state['estimate'], 100):.0f}% used "
            f"({state['spent']:,} tokens at {state['per_pct']:,.0f}/%, "
            f"{state['backing']} reading{'s' if state['backing'] != 1 else ''}), "
            f"renews {uc.stamp(state['renews'])} in {uc.duration(state['renews'] - uc.now)}"
        )


try:
    main()
except Exception:  # a bug here must never be able to lock someone out of their own session
    sys.exit(0)
