#!/usr/bin/env python3
"""Summarize the shared credit window for SessionStart context.

Invoked by usage-window.sh with REPO_DIR set. Reads the hook's JSON payload on
stdin for `session_id` and `transcript_path`: several agents append to one log,
so every line this writes is tagged with the session that wrote it.

Also logs the window's boundary when the log does not already know it — the
one place that happens, since a fresh SessionStart is the only invocation that
runs once per session rather than once per prompt.
"""

import argparse
import sys
from datetime import timedelta

import usage_common as uc


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize the shared credit window.")
    parser.add_argument("--session", help="session id to tag anything this run appends to the log")
    parser.add_argument("--transcript", help="transcript to weigh instead of the one on stdin")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = uc.hook_payload()
    session_id = args.session or payload.get("session_id") or None
    transcript = args.transcript or payload.get("transcript_path") or None

    events = uc.read_events()
    state = uc.window_state(events)
    # Persisted here, ahead of every dispatch: a window that turns over mid-session
    # is only ever noticed by the gate (run on every prompt), never by a fresh
    # SessionStart, so logging it only here would leave it unrecorded for the
    # rest of that session — this is the one call site that runs once per session.
    if state["unlogged"]:
        uc.log_boundary(session_id, state["window_start"])

    out = []

    window_start = state["window_start"]
    opened = " (this session opened it)" if state["opened"] else ""
    requests, sessions = state["requests"], state["sessions"]
    totals, by_model, spent = state["totals"], state["by_model"], state["spent"]
    renews, basis = state["renews"], state["basis"]

    out.append(
        f"  window   started {uc.stamp(window_start)}, {uc.duration(uc.now - window_start)} ago{opened}"
    )
    if renews > uc.now:
        out.append(f"  renews   {uc.stamp(renews)}, in {uc.duration(renews - uc.now)} ({basis})")
    else:
        out.append(
            f"  renews   {uc.stamp(renews)} — that has passed, so the window should have reset "
            f"already ({basis}); the next session start records the new one"
        )
    if requests:
        breakdown = ", ".join(f"{name} {totals[name]:,}" for name, _ in uc.TOKEN_FIELDS)
        out.append(
            f"  spent    {spent:,} tokens over {len(requests)} requests in "
            f"{len(sessions)} session{'s' if len(sessions) != 1 else ''} ({breakdown})"
        )
        if len(by_model) > 1:
            mix = ", ".join(
                f"{model or 'unknown'} {count:,}"
                for model, count in sorted(by_model.items(), key=lambda kv: -kv[1])
            )
            out.append(f"  models   {mix} — models are not priced alike, so this total is a mix")
    else:
        out.append("  spent    no transcript traffic recorded in this window yet")

    # A resumed session sees what it is carrying before the next prompt is gated
    # on it, rather than being surprised by the refusal.
    carry = uc.session_carry(transcript) if transcript else None
    if carry:
        context, last, _first = carry
        idle = (uc.now - last).total_seconds() / 60
        if idle >= uc.CACHE_TTL_MINUTES and context:
            gated = " — at or above that, the next prompt asks you to clear" if context >= uc.CARRY_AT else ""
            out.append(
                f"  carried  this session has been idle {uc.duration(uc.now - last)}, past the "
                f"prompt-cache TTL, and holds {context:,} tokens of history (threshold "
                f"{uc.CARRY_AT:,}{gated})"
            )

    last, per_pct = state["last"], state["per_pct"]

    if per_pct:
        estimate = state["estimate"]
        fitted = (
            f"fitted on {state['backing']} readings"
            if state["backing"] >= 2
            else f"from the single {last['pct']}% reading at {uc.stamp(last['_t'])}, which cannot "
                 "separate spend the scan misses from the rate — treat it as a guess"
        )
        line = (
            f"  estimate ~{min(estimate, 100):.0f}% used, {per_pct:,.0f} tokens/% {fitted}"
        )
        if estimate >= 100:
            line += "; that calibration says the window is already spent — expect a refusal, and "
            line += "ask for a fresh reading before trusting it"
        else:
            # Prefer the rate since the last reading: it reflects how many agents
            # are running now. Fall back to the window average only when that span
            # is too short, and say so, because it embeds bursts already over.
            rate = uc.tokens_per_minute(requests, last["_t"], uc.now)
            span = f"the {uc.duration(uc.now - last['_t'])} since that reading"
            if not rate:
                elapsed = (uc.now - window_start).total_seconds() / 60
                rate = spent / elapsed if elapsed > 0 else 0
                span = "the whole window, which still counts agents that have since stopped"
            if rate:
                empty = uc.now + timedelta(minutes=(100 - estimate) * per_pct / rate)
                verdict = "before renewal — pace or stop early" if empty < renews else "after renewal"
                line += f"; at the rate over {span}, credit runs out {uc.stamp(empty)} ({verdict})"
        out.append(line)
    elif last:
        out.append(
            f"  estimate none — the {last['pct']}% reported at {uc.stamp(last['_t'])} cannot be "
            "calibrated: no transcript traffic was recorded before it. A later report will fix this."
        )
    else:
        out.append(
            "  estimate none — tokens cannot be converted to a percentage until the user reports "
            'one. Ask for "X% used, renews in Y minutes" before any long unattended run, and log '
            "it as a usage-report event."
        )

    print("Shared credit window (computed by a SessionStart hook; no request was spent):")
    print("\n".join(out))
    tag = (
        f', tagged "session":"{session_id}" so a line can be traced back to the agent that wrote it'
        if session_id else ""
    )
    print(f"  log      {uc.EVENTS_PATH} — append what you observe{tag}; conclusions go in usage/notes.md")


try:
    main()
except Exception:  # a session must never fail to start because of this hook
    sys.exit(0)
