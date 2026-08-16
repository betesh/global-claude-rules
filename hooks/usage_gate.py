#!/usr/bin/env python3
"""Decide whether a prompt is worth sending, before it is sent.

Invoked by usage-gate.sh with REPO_DIR set, on every UserPromptSubmit. The
SessionStart report (usage_report.py) runs once, before a session has spent
anything, so nothing watches the window while it actually drains. This runs on
every prompt, off the same fitted estimate, and is the only place a spent
window can be noticed for free — once the model is invoked the request is
already paid for, so a rule telling it to stop cannot un-spend one.

Exit codes are the whole interface:

  2  credit is gone, or this session should clear before paying for a cache
     rewrite; the harness drops the prompt and shows our stderr
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


def carried_reason(events, session_id, transcript):
    """Why this session should clear before paying for a full cache rewrite, or
    None.

    Both conditions are required. A session idle less than the TTL still has a
    warm cache, so its next request is a cheap cache-read regardless of size —
    clearing it would only add the interruption with no saving behind it. A
    session that simply grew large while staying continuously active has no
    idle gap at all, so the rewrite isn't coming either. Only a session that is
    both idle past the TTL and big enough to matter is about to pay for the
    rewrite whether or not it clears, which is what makes that moment free to
    interrupt.
    """
    if os.environ.get("CLAUDE_CARRIED_CONTEXT_OK") == "1" or not transcript:
        return None
    carry = uc.session_carry(transcript)
    if not carry:
        return None
    context, _weighted, last, _first = carry
    idle = (uc.now - last).total_seconds() / 60
    if idle < uc.CACHE_TTL_MINUTES or context < uc.CARRY_AT:
        return None
    # Re-submitting is the acknowledgement: that request lands in the
    # transcript and moves `last` forward, so the same idle crossing can never
    # ask twice. Nobody is locked out of their own session by a threshold that
    # turns out to be wrong.
    for event in events:
        if (event.get("kind") == "cache-expired" and event.get("session") == session_id
                and event["_t"] >= last):
            return None

    return (
        f"this session has been idle {uc.duration(uc.now - last)}, longer than the "
        f"~{uc.CACHE_TTL_MINUTES:.0f}-minute prompt-cache TTL, and is holding {context:,} tokens of "
        "history. The next request pays a full cache rewrite of roughly that many tokens to "
        "re-establish what a cache-read would otherwise cover far more cheaply — clearing now "
        "costs nothing extra, since that rewrite is coming either way. Before telling the user "
        "it is safe to /clear: check `git status` in every repo touched this session, not just "
        "the working directory; and write down anything learned this session that would "
        "otherwise be re-explained next time — as a rule, that project's CLAUDE.md, or a plan "
        f"file under {os.path.join(uc.REPO_DIR, 'docs/plans')}, following the routing in "
        "`rules/no-memory-directory.md` (never into `~/.claude/projects/*/memory/`). Do all of "
        "this in as few tool calls as possible: context is at its largest right now, so every "
        "call this session costs more than it will again until the next /clear."
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

    reason = uc.gate_reason(state)
    if reason:
        why, until = reason
        print(
            f"Credit is out: {why}. Not sending this request. The window renews at "
            f"{uc.stamp(until)}, {uc.duration(until - uc.now)} from now — wait until then, or set "
            f"CLAUDE_USAGE_GATE_PCT above {uc.GATE_AT_PCT:.0f} to override. Wait with a plain "
            "foreground `sleep` (chained in pieces if the shell caps a single call short of the "
            "full wait) — never `run_in_background`: a backgrounded wait's completion does not "
            "resume an idle session by itself, so the wait never actually ends.",
            file=sys.stderr,
        )
        sys.exit(2)

    carried = carried_reason(events, session_id, transcript)
    if carried:
        event = {"kind": "cache-expired"}
        pid = uc.claude_pid()
        if pid:
            event["claude_pid"] = pid
        uc.append_event(session_id, event)
        print(
            f"{carried} Use /clear if the next task does not depend on this conversation, or "
            "/compact if the work must continue here. To keep it anyway, send the prompt again — "
            "this asks once per idle crossing — or set CLAUDE_CARRIED_CONTEXT_OK=1 for a run that "
            "cannot answer a prompt.",
            file=sys.stderr,
        )
        sys.exit(2)

    if state["estimate"] is not None:
        print(
            f"credit ~{min(state['estimate'], 100):.0f}% used "
            f"({state['weighted_spent']:,.0f} weighted-tok at {state['per_pct']:,.0f}/%, "
            f"{state['backing']} reading{'s' if state['backing'] != 1 else ''}), "
            f"renews {uc.stamp(state['renews'])} in {uc.duration(state['renews'] - uc.now)}"
        )


try:
    main()
except Exception:  # a bug here must never be able to lock someone out of their own session
    sys.exit(0)
